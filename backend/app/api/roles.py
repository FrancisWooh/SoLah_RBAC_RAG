from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.role import Role
from app.models.user import User
from app.services.role_admin import list_roles

router = APIRouter()


@router.get("")
def get_available_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Any authenticated user can see the role catalog (id/name only) —
    needed so they can pick a role to request in POST /api/role-requests.
    Full role detail (approver_role etc.) stays admin-only via
    GET /api/admin/roles."""
    roles: list[Role] = list_roles(db)
    return [{"id": r.id, "name": r.name} for r in roles]
