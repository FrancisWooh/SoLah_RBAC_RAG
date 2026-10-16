from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_effective_roles
from app.core.db import get_db
from app.models.document import Document
from app.models.user import User
from app.services import cos_storage
from app.services.audit import append_audit_log
from app.services.vectorstore.base import PermissionContext
from app.services.vectorstore.rbac_filter import is_permitted

router = APIRouter()


class DocumentLinkResponse(BaseModel):
    url: str
    filename: str
    expires_in: int


def _audit_view(db: Session, user: User, roles: set[str], doc_id: str, decision: str, reason: str | None) -> None:
    append_audit_log(
        db,
        event_type="doc_view",
        user_id=user.id,
        effective_roles=sorted(roles),
        filter_applied={
            "roles": sorted(roles),
            "clearance": user.clearance,
            "compartments": sorted(user.compartments),
        },
        # An allowed view lists the document; a denied one records it as blocked (audit-only, as for queries).
        retrieved_doc_ids=[doc_id] if decision == "allow" else [],
        blocked_doc_ids=[doc_id] if decision == "deny" else [],
        decision=decision,
        deny_reason=reason,
    )
    db.commit()


@router.get("/{doc_id}/link", response_model=DocumentLinkResponse)
def document_link(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    effective_roles: set[str] = Depends(get_current_user_effective_roles),
    db: Session = Depends(get_db),
):
    """Short-lived link to the original file, for checking an answer against its source.

    Unknown, archived/deleted, not-a-file and not-permitted documents all give the
    same 404, so the response never confirms that a restricted document exists.
    Every attempt is written to the audit log."""
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在或无权访问")

    if not cos_storage.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "原文存储未配置")

    doc = db.get(Document, doc_id)
    permission = PermissionContext(
        roles=effective_roles,
        clearance=current_user.clearance,
        compartments=set(current_user.compartments),
    )
    permitted = (
        doc is not None
        and doc.status == "active"
        and is_permitted(doc.allowed_roles or [], doc.required_clearance, doc.compartments or [], permission)
    )
    if not permitted:
        _audit_view(db, current_user, effective_roles, doc_id, "deny", "doc_view: not found or not permitted")
        raise not_found

    key = cos_storage.object_key(doc.source_ref)
    if key is None:
        raise not_found

    filename = doc.source_ref.rsplit("/", 1)[-1]
    url = cos_storage.presigned_url(key, filename)
    _audit_view(db, current_user, effective_roles, doc_id, "allow", None)
    return DocumentLinkResponse(url=url, filename=filename, expires_in=cos_storage.settings.cos_url_expire_seconds)
