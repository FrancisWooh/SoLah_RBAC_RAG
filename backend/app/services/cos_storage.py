"""Presigned links to the original documents kept in a Tencent COS bucket.

The bucket must be PRIVATE: access control lives in the API (see
app/api/documents.py), which only calls presigned_url() after the same RBAC
check the retrieval pipeline uses. A public bucket would bypass it entirely.
"""

from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import quote

from app.core.config import settings

LIBRARY_REF_PREFIX = "/company_share/"
INLINE_EXTENSIONS = {".pdf"}  # browsers render these; everything else is downloaded


class CosNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.cos_bucket and settings.cos_region and settings.cos_secret_id and settings.cos_secret_key)


@lru_cache
def _client():
    from qcloud_cos import CosConfig, CosS3Client

    return CosS3Client(
        CosConfig(
            Region=settings.cos_region,
            SecretId=settings.cos_secret_id,
            SecretKey=settings.cos_secret_key,
            Scheme="https",
        )
    )


def object_key(source_ref: str | None) -> str | None:
    """Documents registered from the library have source_ref '/company_share/<rel>';
    anything else (e.g. rows synced from a department database) has no file."""
    if not source_ref or not source_ref.startswith(LIBRARY_REF_PREFIX):
        return None
    rel = source_ref[len(LIBRARY_REF_PREFIX):]
    if not rel or ".." in PurePosixPath(rel).parts:
        return None
    return settings.cos_prefix + rel


def presigned_url(key: str, filename: str) -> str:
    if not is_configured():
        raise CosNotConfigured("COS is not configured")
    disposition = "inline" if PurePosixPath(filename).suffix.lower() in INLINE_EXTENSIONS else "attachment"
    return _client().get_presigned_url(
        Method="GET",
        Bucket=settings.cos_bucket,
        Key=key,
        Expired=settings.cos_url_expire_seconds,
        Params={"response-content-disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"},
    )
