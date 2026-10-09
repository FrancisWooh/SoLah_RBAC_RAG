import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.redis_client import redis_client
from app.core.security import InvalidTokenError, decode_access_token
from app.models.user import User
from app.services.rbac import get_effective_roles_cached

_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Trusts the JWT only for identity (sub). clearance/compartments/roles
    are always re-read from Postgres (roles via the 30s cache), so a change
    made by an admin shows up on the user's very next request instead of
    waiting for the token to expire.
    """
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效或已过期的登录凭证")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效的登录凭证")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")

    return user


def get_current_user_effective_roles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> set[str]:
    return get_effective_roles_cached(db, redis_client, current_user.id)


def require_roles(*allowed_roles: str):
    """Dependency factory: 403s unless the caller's effective roles overlap
    `allowed_roles`. Use for every /api/admin/* endpoint — readme.txt's
    "/admin 入口，需 admin/approver 角色" requirement."""

    def _check(
        current_user: User = Depends(get_current_user),
        effective_roles: set[str] = Depends(get_current_user_effective_roles),
    ) -> User:
        if not set(allowed_roles) & effective_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足，需要管理员角色")
        return current_user

    return _check
