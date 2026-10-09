"""IdP login reconcile: keep user_roles in sync with the IdP on every login.

When a user logs in, the IdP adapter returns their current group
memberships. We map those to local role_ids and do a full reconcile of
``source='permanent', source_ref LIKE 'idp:%'`` grants:

  - roles the IdP says the user has but DB doesn't  -> grant
  - roles the DB has (idp-sourced) but IdP doesn't   -> revoke
  - roles in both                                     -> leave as-is

Directly-assigned roles (source_ref=None), project roles (source='project')
and temporary roles (source='temporary') are never touched by reconcile.

This does NOT reuse grant_role/revoke_role from role_admin.py because those
require a human actor (granted_by: UUID) and commit internally. The IdP
reconcile has no human actor and needs a single atomic commit.
"""

import uuid

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.user_role import UserRole
from app.services.audit import append_audit_log
from app.services.idp.factory import get_idp_adapter
from app.services.idp.group_mapping import load_group_role_map, map_groups_to_roles
from app.services.rbac import invalidate_effective_roles_cache

IDP_SOURCE_REF_PREFIX = "idp:"


def reconcile_user_with_idp(
    db: Session,
    redis_client: Redis,
    *,
    username: str,
) -> User:
    """Full IdP login + reconcile flow. Called by the /login endpoint.

    1. Call IdP adapter to get user info + groups (raises
       IdPAuthenticationError if the IdP doesn't recognise the user)
    2. JIT provisioning: create User row if not exists, update profile
       fields if it does
    3. Map IdP groups -> local role_ids
    4. Full reconcile of source='permanent', source_ref LIKE 'idp:%' rows
    5. Invalidate role cache
    6. Return the User (caller issues JWT)
    """
    adapter = get_idp_adapter()
    idp_info = adapter.authenticate(username)

    group_role_map = load_group_role_map(
        settings.idp_group_role_map_path or None
    )

    # Map groups to roles: {role_id: group_name}
    idp_role_to_group = map_groups_to_roles(idp_info.idp_groups, group_role_map)
    idp_role_ids = set(idp_role_to_group.keys())

    # JIT provisioning: find or create user
    user = db.scalar(select(User).where(User.username == idp_info.username))
    if user is None:
        user = User(
            username=idp_info.username,
            email=idp_info.email,
            department=idp_info.department,
            clearance=1,
            compartments=[],
        )
        db.add(user)
        db.flush()
    else:
        # Update profile fields from IdP (email/department may change)
        if idp_info.email:
            user.email = idp_info.email
        if idp_info.department:
            user.department = idp_info.department

    # Fetch existing IdP-sourced role grants for this user
    existing_idp_grants = db.scalars(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.source == "permanent",
            UserRole.source_ref.like(f"{IDP_SOURCE_REF_PREFIX}%"),
            UserRole.status == "active",
        )
    ).all()

    # Build {role_id: UserRole} from existing grants
    existing_role_to_grant = {g.role_id: g for g in existing_idp_grants}

    # Reconcile: three-way set diff
    roles_to_grant = idp_role_ids - set(existing_role_to_grant.keys())
    roles_to_revoke = set(existing_role_to_grant.keys()) - idp_role_ids

    # Grant new roles
    for role_id in roles_to_grant:
        group_name = idp_role_to_group[role_id]
        db.add(
            UserRole(
                user_id=user.id,
                role_id=role_id,
                source="permanent",
                source_ref=f"{IDP_SOURCE_REF_PREFIX}{group_name}",
                end_at=None,
                status="active",
            )
        )
        _write_idp_audit(
            db, "role_grant_idp", user.id, role_id,
            extra_reason=f"idp_group:{group_name}",
        )

    # Revoke removed roles
    for role_id in roles_to_revoke:
        grant = existing_role_to_grant[role_id]
        grant.status = "revoked"
        _write_idp_audit(
            db, "role_revoke_idp", user.id, role_id,
            extra_reason=f"idp_group_removed:{grant.source_ref}",
        )

    db.commit()
    invalidate_effective_roles_cache(redis_client, user.id)
    return user


def _write_idp_audit(
    db: Session,
    event_type: str,
    target_user_id: uuid.UUID,
    role_id: str,
    extra_reason: str | None = None,
) -> None:
    append_audit_log(
        db,
        event_type=event_type,
        user_id=None,  # system-driven, not a human actor
        decision="allow",
        deny_reason=extra_reason,
        filter_applied={"target_user_id": str(target_user_id), "role_id": role_id},
    )
