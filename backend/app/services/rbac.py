import json
import uuid
from datetime import datetime

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_role import UserRole

ROLE_CACHE_TTL_SECONDS = 30


def _role_cache_key(user_id: uuid.UUID) -> str:
    return f"effective_roles:{user_id}"


def invalidate_effective_roles_cache(redis_client: Redis, user_id: uuid.UUID) -> None:
    """Call this right after any grant/revoke/expire write to user_roles."""
    redis_client.delete(_role_cache_key(user_id))


def get_effective_roles_cached(
    db: Session, redis_client: Redis, user_id: uuid.UUID
) -> set[str]:
    """Same result as get_effective_roles(as_of=now), fronted by a short-TTL
    cache so permission checks don't hit Postgres on every query. Grant/revoke
    endpoints must call invalidate_effective_roles_cache() so a change is
    visible well before the TTL would otherwise expire it.
    """
    key = _role_cache_key(user_id)
    cached = redis_client.get(key)
    if cached is not None:
        return set(json.loads(cached))

    roles = get_effective_roles(db, user_id)
    redis_client.setex(key, ROLE_CACHE_TTL_SECONDS, json.dumps(sorted(roles)))
    return roles


def get_effective_roles(
    db: Session, user_id: uuid.UUID, as_of: datetime | None = None
) -> set[str]:
    """Effective roles = permanent + not-yet-expired temporary/project grants.

    A grant counts only when status == 'active' and either end_at is NULL
    (permanent) or end_at is in the future relative to `as_of` (defaults to
    now). Expiry is evaluated here at query time rather than via a background
    job, per the spec's "动态计算有效角色" requirement.
    """
    now = as_of or datetime.utcnow()
    rows = db.scalars(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.status == "active",
        )
    ).all()
    return {
        row.role_id for row in rows if row.end_at is None or row.end_at > now
    }
