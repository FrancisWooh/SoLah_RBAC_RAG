"""Mirror the document library from the Tencent COS bucket into DATA_DIR (COS is the source of truth).

New and changed objects are downloaded, objects that no longer exist in COS are deleted locally, so
deleting a file in the bucket removes it from the knowledge base a few minutes later (the library
watcher notices the missing file and archives / restores versions as usual).

Because it deletes local files, it is deliberately cautious:
  * it refuses to run when the bucket listing is empty or has no manifest.json
  * it refuses to delete more than --max-delete files in one run (default 3) unless --force
  * downloads go to a temporary name and are renamed into place, so the watcher never sees a half file
  * unsafe keys (.., absolute paths) and Windows "Zone.Identifier" leftovers are ignored
  * two runs never overlap (lock file)

Usage (needs COS_* in backend/.env; read-only COS permissions are enough):
  docker compose exec -T backend python sync_data_from_cos.py             sync
  docker compose exec -T backend python sync_data_from_cos.py --dry-run   show what would change
Exit status: 0 ok, 1 error, 2 deletions were blocked by the safety limit.

Cron (every 5 minutes), see README_EN.md.
"""

import argparse
import fcntl
import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from app.core.config import settings

TEMP_SUFFIX = ".cos-part"  # not a supported document extension, so the library watcher ignores it
LOCK_PATH = "/tmp/cos_sync.lock"
_MD5 = re.compile(r"^[0-9a-f]{32}$")


@dataclass
class Result:
    downloaded: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: int = 0
    skipped: list[str] = field(default_factory=list)
    blocked_deletes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _ignored(rel: str) -> bool:
    name = PurePosixPath(rel).name
    return "Zone.Identifier" in name or name.endswith(TEMP_SUFFIX) or name == ".DS_Store"


def _safe(rel: str) -> bool:
    p = PurePosixPath(rel)
    return bool(rel) and not p.is_absolute() and ".." not in p.parts


def list_remote(client, bucket: str, prefix: str) -> dict[str, tuple[int, str]]:
    """relative path -> (size, etag) for every object under prefix (directory placeholders skipped)."""
    out, marker = {}, ""
    while True:
        r = client.list_objects(Bucket=bucket, Prefix=prefix, Marker=marker, MaxKeys=1000)
        for o in r.get("Contents", []):
            key = o["Key"]
            if not key.endswith("/"):
                out[key[len(prefix):]] = (int(o["Size"]), str(o["ETag"]).strip('"'))
        if str(r.get("IsTruncated")).lower() == "true":
            marker = r["NextMarker"]
        else:
            return out


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _same(path: Path, size: int, etag: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    # a plain upload's ETag is the MD5; multipart ETags ("<md5>-<n>") cannot be compared, size has to do
    return _md5(path) == etag if _MD5.match(etag) else True


def _local_files(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file() and not _ignored(p.relative_to(root).as_posix())
    }


def sync(client, bucket: str, prefix: str, root: Path, *, dry_run=False, max_delete=3, force=False) -> Result:
    res = Result()
    remote = {k: v for k, v in list_remote(client, bucket, prefix).items() if not _ignored(k)}
    if not remote:
        res.errors.append("bucket listing is empty; refusing to sync (would delete the whole library)")
        return res
    if "manifest.json" not in remote:
        res.errors.append("manifest.json is not in the bucket; refusing to sync")
        return res

    root.mkdir(parents=True, exist_ok=True)
    local = _local_files(root)

    for rel, (size, etag) in sorted(remote.items()):
        if not _safe(rel):
            res.skipped.append(f"{rel}: unsafe path")
            continue
        dest = root / rel
        if _same(dest, size, etag):
            res.unchanged += 1
            continue
        (res.updated if dest.exists() else res.downloaded).append(rel)
        if dry_run:
            continue
        tmp = dest.with_name(dest.name + TEMP_SUFFIX)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            client.get_object(Bucket=bucket, Key=prefix + rel)["Body"].get_stream_to_file(str(tmp))
            if tmp.stat().st_size != size:
                tmp.unlink(missing_ok=True)
                raise OSError(f"size mismatch after download ({tmp.stat().st_size if tmp.exists() else '?'} != {size})")
            os.replace(tmp, dest)
        except Exception as e:  # keep going: one bad object must not stop the rest
            tmp.unlink(missing_ok=True)
            (res.updated if rel in res.updated else res.downloaded).remove(rel)
            res.errors.append(f"{rel}: {e}")

    gone = sorted(set(local) - set(remote))
    if len(gone) > max_delete and not force:
        res.blocked_deletes = gone
        return res
    for rel in gone:
        res.deleted.append(rel)
        if not dry_run:
            (root / rel).unlink(missing_ok=True)
            parent = (root / rel).parent
            while parent != root and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    return res


def _make_client():
    from qcloud_cos import CosConfig, CosS3Client

    return CosS3Client(
        CosConfig(Region=settings.cos_region, SecretId=settings.cos_secret_id, SecretKey=settings.cos_secret_key, Scheme="https")
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="only report what would change")
    ap.add_argument("--max-delete", type=int, default=3, help="refuse to delete more local files than this in one run")
    ap.add_argument("--force", action="store_true", help="ignore --max-delete")
    args = ap.parse_args(argv)

    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if not (settings.cos_bucket and settings.cos_region and settings.cos_secret_id and settings.cos_secret_key):
        print(f"[{stamp}] COS is not configured (COS_* in backend/.env)")
        return 1

    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"[{stamp}] another sync is running; skipped")
        return 0

    res = sync(_make_client(), settings.cos_bucket, settings.cos_prefix, Path(settings.data_dir),
               dry_run=args.dry_run, max_delete=args.max_delete, force=args.force)
    tag = " (dry run)" if args.dry_run else ""
    print(f"[{stamp}] cos sync{tag}: new={len(res.downloaded)} updated={len(res.updated)} deleted={len(res.deleted)} "
          f"unchanged={res.unchanged} skipped={len(res.skipped)} errors={len(res.errors)}")
    for label, items in (("new", res.downloaded), ("updated", res.updated), ("deleted", res.deleted), ("skipped", res.skipped)):
        for i in items:
            print(f"  {label:8} {i}")
    for e in res.errors:
        print(f"  ERROR    {e}")
    if res.blocked_deletes:
        print(f"  BLOCKED  {len(res.blocked_deletes)} local file(s) are not in COS but the limit is {args.max_delete}; "
              f"nothing was deleted. Check the bucket, then run with --force if this is intended:")
        for i in res.blocked_deletes:
            print(f"           {i}")
        return 2
    return 1 if res.errors else 0


if __name__ == "__main__":
    sys.exit(main())
