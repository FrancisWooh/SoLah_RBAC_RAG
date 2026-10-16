"""sync_data_from_cos: mirror a COS prefix into the library directory, with guards around deletion.
Uses an in-memory fake of the COS client; no network."""

import hashlib

import pytest

import sync_data_from_cos as cs

PREFIX = "data/"


class FakeBody:
    def __init__(self, data):
        self.data = data

    def get_stream_to_file(self, path):
        with open(path, "wb") as f:
            f.write(self.data)


class FakeCos:
    def __init__(self, objects):  # {key: bytes}
        self.objects = dict(objects)
        self.fail_get = set()

    def list_objects(self, Bucket, Prefix, Marker="", MaxKeys=1000):
        keys = sorted(k for k in self.objects if k.startswith(Prefix) and k > Marker)
        page, rest = keys[:2], keys[2:]  # tiny pages exercise the pagination
        return {
            "Contents": [{"Key": k, "Size": str(len(self.objects[k])), "ETag": f'"{hashlib.md5(self.objects[k]).hexdigest()}"'} for k in page],
            "IsTruncated": "true" if rest else "false",
            "NextMarker": page[-1] if page else "",
        }

    def get_object(self, Bucket, Key):
        if Key in self.fail_get:
            raise RuntimeError("boom")
        return {"Body": FakeBody(self.objects[Key])}


def _cos(**files):
    return FakeCos({PREFIX + k.replace("__", "/"): v for k, v in files.items()})


def run(client, root, **kw):
    return cs.sync(client, "b", PREFIX, root, **kw)


def test_downloads_new_files_and_creates_directories(tmp_path):
    client = FakeCos({PREFIX + "manifest.json": b"[]", PREFIX + "hr/a.docx": b"A", PREFIX + "legal/b.pdf": b"B"})

    res = run(client, tmp_path)

    assert sorted(res.downloaded) == ["hr/a.docx", "legal/b.pdf", "manifest.json"] and not res.errors
    assert (tmp_path / "hr/a.docx").read_bytes() == b"A"
    assert not list(tmp_path.rglob("*" + cs.TEMP_SUFFIX))


def test_second_run_changes_nothing(tmp_path):
    client = FakeCos({PREFIX + "manifest.json": b"[]", PREFIX + "hr/a.docx": b"A"})
    run(client, tmp_path)
    mtime = (tmp_path / "hr/a.docx").stat().st_mtime_ns

    res = run(client, tmp_path)

    assert res.unchanged == 2 and not (res.downloaded or res.updated or res.deleted)
    assert (tmp_path / "hr/a.docx").stat().st_mtime_ns == mtime  # untouched, so the watcher sees no change


def test_changed_object_is_replaced(tmp_path):
    client = FakeCos({PREFIX + "manifest.json": b"[]", PREFIX + "hr/a.docx": b"old"})
    run(client, tmp_path)
    client.objects[PREFIX + "hr/a.docx"] = b"newer content"

    res = run(client, tmp_path)

    assert res.updated == ["hr/a.docx"]
    assert (tmp_path / "hr/a.docx").read_bytes() == b"newer content"


def test_object_deleted_in_cos_is_deleted_locally(tmp_path):
    client = FakeCos({PREFIX + "manifest.json": b"[]", PREFIX + "hr/a.docx": b"A", PREFIX + "hr/b.docx": b"B"})
    run(client, tmp_path)
    del client.objects[PREFIX + "hr/b.docx"]

    res = run(client, tmp_path)

    assert res.deleted == ["hr/b.docx"]
    assert not (tmp_path / "hr/b.docx").exists() and (tmp_path / "hr/a.docx").exists()


def test_emptied_directory_is_removed(tmp_path):
    client = FakeCos({PREFIX + "manifest.json": b"[]", PREFIX + "legal/only.pdf": b"x"})
    run(client, tmp_path)
    del client.objects[PREFIX + "legal/only.pdf"]

    run(client, tmp_path)

    assert not (tmp_path / "legal").exists()


def test_mass_deletion_is_blocked(tmp_path):
    files = {PREFIX + "manifest.json": b"[]"} | {PREFIX + f"d/f{i}.pdf": b"x" for i in range(6)}
    client = FakeCos(files)
    run(client, tmp_path)
    client.objects = {PREFIX + "manifest.json": b"[]"}  # e.g. someone emptied the folder by mistake

    res = run(client, tmp_path, max_delete=3)

    assert len(res.blocked_deletes) == 6 and not res.deleted
    assert len(list((tmp_path / "d").glob("*.pdf"))) == 6  # nothing was removed

    forced = run(client, tmp_path, max_delete=3, force=True)
    assert len(forced.deleted) == 6


def test_empty_bucket_or_missing_manifest_is_refused(tmp_path):
    (tmp_path / "keep.pdf").write_bytes(b"x")

    assert run(FakeCos({}), tmp_path).errors
    assert run(FakeCos({PREFIX + "hr/a.docx": b"A"}), tmp_path).errors  # no manifest.json
    assert (tmp_path / "keep.pdf").exists()


def test_dry_run_touches_nothing(tmp_path):
    (tmp_path / "stale.pdf").write_bytes(b"x")
    client = FakeCos({PREFIX + "manifest.json": b"[]", PREFIX + "hr/a.docx": b"A"})

    res = run(client, tmp_path, dry_run=True, max_delete=5)

    assert res.downloaded and res.deleted == ["stale.pdf"]
    assert not (tmp_path / "hr").exists() and (tmp_path / "stale.pdf").exists()


def test_junk_and_unsafe_keys_are_ignored(tmp_path):
    client = FakeCos({
        PREFIX + "manifest.json": b"[]",
        PREFIX + "hr/a.docx:Zone.Identifier": b"z",
        PREFIX + "hr/a.docxZone.Identifier": b"z",
        PREFIX + "../escape.txt": b"x",
        PREFIX + "hr/": b"",  # directory placeholder
    })

    res = run(client, tmp_path)

    assert res.downloaded == ["manifest.json"]
    assert [p.name for p in tmp_path.rglob("*") if p.is_file()] == ["manifest.json"]
    assert not (tmp_path.parent / "escape.txt").exists()
    assert any("unsafe" in s for s in res.skipped)


def test_failed_download_leaves_no_partial_file_and_keeps_going(tmp_path):
    client = FakeCos({PREFIX + "manifest.json": b"[]", PREFIX + "hr/a.docx": b"A", PREFIX + "hr/b.docx": b"B"})
    client.fail_get.add(PREFIX + "hr/a.docx")

    res = run(client, tmp_path)

    assert len(res.errors) == 1 and "hr/a.docx" in res.errors[0]
    assert (tmp_path / "hr/b.docx").read_bytes() == b"B"
    assert not (tmp_path / "hr/a.docx").exists() and not list(tmp_path.rglob("*" + cs.TEMP_SUFFIX))


def test_local_junk_files_are_never_deleted_or_counted(tmp_path):
    (tmp_path / "x.docx:Zone.Identifier").write_bytes(b"z")
    client = FakeCos({PREFIX + "manifest.json": b"[]"})

    res = run(client, tmp_path, max_delete=0)

    assert not res.deleted and not res.blocked_deletes
