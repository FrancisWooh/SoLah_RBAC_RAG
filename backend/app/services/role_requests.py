import uuid
from datetime import datetime, timedelta

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.role_request import RoleRequest
from app.services.role_admin import RoleAdminError, grant_role


def submit_role_request(
    db: Session,
    *,
    requester_id: uuid.UUID,
    role_id: str,
    reason: str,
    source_ref: str | None,
    requested_duration: timedelta | None,
) -> RoleRequest:
    if db.get(Role, role_id) is None:
        raise RoleAdminError(f"角色不存在：{role_id}")

    request = RoleRequest(
        requester_id=requester_id,
        role_id=role_id,
        reason=reason,
        source_ref=source_ref,
        requested_duration=requested_duration,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_role_requests(db: Session, *, status: str | None = None) -> list[RoleRequest]:
    stmt = select(RoleRequest).order_by(RoleRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(RoleRequest.status == status)
    return list(db.scalars(stmt))


def list_my_role_requests(db: Session, requester_id: uuid.UUID) -> list[RoleRequest]:
    return list(
        db.scalars(
            select(RoleRequest)
            .where(RoleRequest.requester_id == requester_id)
            .order_by(RoleRequest.created_at.desc())
        )
    )


def _get_pending_request(db: Session, request_id: int) -> RoleRequest:
    request = db.get(RoleRequest, request_id)
    if request is None:
        raise RoleAdminError(f"角色申请不存在：{request_id}")
    if request.status != "pending":
        raise RoleAdminError(f"该申请已处理（当前状态：{request.status}），不能重复操作")
    return request


def approve_role_request(
    db: Session, redis_client: Redis, *, request_id: int, approver_id: uuid.UUID
) -> RoleRequest:
    request = _get_pending_request(db, request_id)

    now = datetime.utcnow()
    end_at = now + request.requested_duration if request.requested_duration else None

    # grant_role() does its own commit + audit log ("role_grant") + cache
    # invalidation — approving a request is just "grant, with provenance".
    grant_role(
        db,
        redis_client,
        user_id=request.requester_id,
        role_id=request.role_id,
        source="temporary",
        source_ref=f"role_request:{request.id}",
        end_at=end_at,
        granted_by=approver_id,
    )

    request.status = "approved"
    request.approver_id = approver_id
    request.approved_at = now
    request.start_at = now
    request.end_at = end_at
    db.commit()
    db.refresh(request)
    return request


def reject_role_request(db: Session, *, request_id: int, approver_id: uuid.UUID) -> RoleRequest:
    request = _get_pending_request(db, request_id)

    request.status = "rejected"
    request.approver_id = approver_id
    request.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    return request
