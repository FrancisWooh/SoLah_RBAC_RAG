import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.core.redis_client import redis_client
from app.models.user import User
from app.schemas.admin_roles import (
    GrantRoleRequest,
    ProjectJoinRequest,
    ProjectLeaveRequest,
    RevokeRoleRequest,
    RoleOut,
    UserOut,
    UserRoleOut,
)
from app.api.role_requests import to_out as role_request_to_out
from app.schemas.role_requests import RoleRequestOut
from app.services.role_admin import (
    RoleAdminError,
    add_project_member,
    grant_role,
    list_roles,
    list_user_roles,
    remove_project_member,
    revoke_role,
)
from app.services.role_requests import approve_role_request, list_role_requests, reject_role_request

router = APIRouter()


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"无效的用户ID：{value}")


@router.get("/roles", response_model=list[RoleOut])
def get_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    return list_roles(db)


@router.get("/users", response_model=list[UserOut])
def get_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    users = db.scalars(select(User).order_by(User.username)).all()
    return [
        UserOut(
            id=str(u.id),
            username=u.username,
            department=u.department,
            clearance=u.clearance,
            compartments=u.compartments,
        )
        for u in users
    ]


@router.get("/users/{user_id}/roles", response_model=list[UserRoleOut])
def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    rows = list_user_roles(db, _parse_uuid(user_id))
    return [
        UserRoleOut(
            id=r.id,
            user_id=str(r.user_id),
            role_id=r.role_id,
            source=r.source,
            source_ref=r.source_ref,
            start_at=r.start_at,
            end_at=r.end_at,
            status=r.status,
        )
        for r in rows
    ]


@router.post("/roles/grant", response_model=UserRoleOut)
def post_grant_role(
    body: GrantRoleRequest,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    try:
        user_role = grant_role(
            db,
            redis_client,
            user_id=_parse_uuid(body.user_id),
            role_id=body.role_id,
            source=body.source,
            source_ref=body.source_ref,
            end_at=body.end_at,
            granted_by=current_user.id,
        )
    except RoleAdminError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return UserRoleOut(
        id=user_role.id,
        user_id=str(user_role.user_id),
        role_id=user_role.role_id,
        source=user_role.source,
        source_ref=user_role.source_ref,
        start_at=user_role.start_at,
        end_at=user_role.end_at,
        status=user_role.status,
    )


@router.post("/roles/revoke", response_model=UserRoleOut)
def post_revoke_role(
    body: RevokeRoleRequest,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    try:
        user_role = revoke_role(
            db, redis_client, user_role_id=body.user_role_id, revoked_by=current_user.id
        )
    except RoleAdminError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    return UserRoleOut(
        id=user_role.id,
        user_id=str(user_role.user_id),
        role_id=user_role.role_id,
        source=user_role.source,
        source_ref=user_role.source_ref,
        start_at=user_role.start_at,
        end_at=user_role.end_at,
        status=user_role.status,
    )


@router.post("/projects/join")
def post_project_join(
    body: ProjectJoinRequest,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    try:
        add_project_member(
            db,
            redis_client,
            project_id=body.project_id,
            user_id=_parse_uuid(body.user_id),
            project_role=body.project_role,
            project_end_at=body.project_end_at,
            added_by=current_user.id,
        )
    except RoleAdminError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return {"status": "ok"}


@router.post("/projects/leave")
def post_project_leave(
    body: ProjectLeaveRequest,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    try:
        remove_project_member(
            db,
            redis_client,
            project_id=body.project_id,
            user_id=_parse_uuid(body.user_id),
            removed_by=current_user.id,
        )
    except RoleAdminError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    return {"status": "ok"}


@router.get("/role-requests", response_model=list[RoleRequestOut])
def get_role_requests(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("platform_admin")),
):
    return [role_request_to_out(r) for r in list_role_requests(db, status=status_filter)]


@router.post("/role-requests/{request_id}/approve", response_model=RoleRequestOut)
def post_approve_role_request(
    request_id: int,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    try:
        request = approve_role_request(
            db, redis_client, request_id=request_id, approver_id=current_user.id
        )
    except RoleAdminError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return role_request_to_out(request)


@router.post("/role-requests/{request_id}/reject", response_model=RoleRequestOut)
def post_reject_role_request(
    request_id: int,
    current_user: User = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
):
    try:
        request = reject_role_request(db, request_id=request_id, approver_id=current_user.id)
    except RoleAdminError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return role_request_to_out(request)
