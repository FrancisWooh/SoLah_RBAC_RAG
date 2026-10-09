import uuid
from datetime import datetime

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_member import ProjectMember
from app.models.role import Role
from app.models.user_role import UserRole
from app.services.audit import append_audit_log
from app.services.rbac import invalidate_effective_roles_cache


class RoleAdminError(Exception):
    """Raised for admin-action misuse (not-found ids etc.) — the API layer
    turns this into a 404/400, never a silent no-op."""


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role)))


def list_user_roles(db: Session, user_id: uuid.UUID) -> list[UserRole]:
    return list(
        db.scalars(
            select(UserRole).where(UserRole.user_id == user_id).order_by(UserRole.created_at.desc())
        )
    )


def _write_audit(
    db: Session,
    event_type: str,
    actor_id: uuid.UUID,
    target_user_id: uuid.UUID,
    role_id: str,
    extra_reason: str | None = None,
) -> None:
    append_audit_log(
        db,
        event_type=event_type,
        user_id=actor_id,
        decision="allow",
        deny_reason=extra_reason,
        filter_applied={"target_user_id": str(target_user_id), "role_id": role_id},
    )


def grant_role(
    db: Session,
    redis_client: Redis,
    *,
    user_id: uuid.UUID,
    role_id: str,
    source: str,
    source_ref: str | None,
    end_at: datetime | None,
    granted_by: uuid.UUID,
) -> UserRole:
    if db.get(Role, role_id) is None:
        raise RoleAdminError(f"角色不存在：{role_id}")

    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        source=source,
        source_ref=source_ref,
        end_at=end_at,
        status="active",
        created_by=granted_by,
    )
    db.add(user_role)
    _write_audit(db, "role_grant", granted_by, user_id, role_id)
    db.commit()
    db.refresh(user_role)

    invalidate_effective_roles_cache(redis_client, user_id)
    return user_role


def revoke_role(
    db: Session, redis_client: Redis, *, user_role_id: int, revoked_by: uuid.UUID
) -> UserRole:
    user_role = db.get(UserRole, user_role_id)
    if user_role is None:
        raise RoleAdminError(f"角色授予记录不存在：{user_role_id}")

    user_role.status = "revoked"
    _write_audit(db, "role_revoke", revoked_by, user_role.user_id, user_role.role_id)
    db.commit()
    db.refresh(user_role)

    invalidate_effective_roles_cache(redis_client, user_role.user_id)
    return user_role


def add_project_member(
    db: Session,
    redis_client: Redis,
    *,
    project_id: str,
    user_id: uuid.UUID,
    project_role: str,
    project_end_at: datetime | None,
    added_by: uuid.UUID,
) -> ProjectMember:
    """Joining a project automatically grants the matching temporary role —
    this is the "project自动授予" path from readme.txt scenario 3, distinct
    from an admin directly granting a role via grant_role() above."""
    if db.get(Role, project_role) is None:
        raise RoleAdminError(f"角色不存在：{project_role}")

    member = db.get(ProjectMember, (project_id, user_id))
    if member is None:
        member = ProjectMember(project_id=project_id, user_id=user_id)
        db.add(member)
    member.project_role = project_role
    member.left_at = None
    member.project_end_at = project_end_at

    db.add(
        UserRole(
            user_id=user_id,
            role_id=project_role,
            source="project",
            source_ref=project_id,
            end_at=project_end_at,
            status="active",
            created_by=added_by,
        )
    )
    _write_audit(db, "role_grant", added_by, user_id, project_role, extra_reason=f"project:{project_id}")
    db.commit()
    db.refresh(member)

    invalidate_effective_roles_cache(redis_client, user_id)
    return member


def remove_project_member(
    db: Session, redis_client: Redis, *, project_id: str, user_id: uuid.UUID, removed_by: uuid.UUID
) -> None:
    member = db.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise RoleAdminError(f"该用户不在项目 {project_id} 中")

    member.left_at = datetime.utcnow()

    active_grants = db.scalars(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.source == "project",
            UserRole.source_ref == project_id,
            UserRole.status == "active",
        )
    ).all()
    for grant in active_grants:
        grant.status = "revoked"
        _write_audit(db, "role_revoke", removed_by, user_id, grant.role_id, extra_reason=f"left project:{project_id}")

    db.commit()
    invalidate_effective_roles_cache(redis_client, user_id)
