from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_effective_roles
from app.core.db import get_db
from app.core.redis_client import redis_client
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.services.idp.base import IdPAuthenticationError
from app.services.idp_reconcile import reconcile_user_with_idp
from app.services.rbac import get_effective_roles_cached

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """IdP-driven login: authenticate via the configured IdP adapter,
    reconcile roles (full reconcile of IdP-sourced grants), then issue
    JWT. With idp_provider='mock' this simulates what a real OIDC/SAML
    callback would do.
    """
    try:
        user = reconcile_user_with_idp(db, redis_client, username=body.username)
    except IdPAuthenticationError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不存在")

    roles = get_effective_roles_cached(db, redis_client, user.id)
    token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "clearance": user.clearance,
            "compartments": user.compartments,
            "roles": sorted(roles),
        }
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(
    current_user: User = Depends(get_current_user),
    effective_roles: set[str] = Depends(get_current_user_effective_roles),
):
    return MeResponse(
        user_id=str(current_user.id),
        username=current_user.username,
        department=current_user.department,
        clearance=current_user.clearance,
        compartments=current_user.compartments,
        effective_roles=sorted(effective_roles),
    )
