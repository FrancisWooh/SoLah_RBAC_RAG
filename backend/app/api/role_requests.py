from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.role_request import RoleRequest
from app.models.user import User
from app.schemas.role_requests import RoleRequestOut, SubmitRoleRequestIn
from app.services.role_admin import RoleAdminError
from app.services.role_requests import list_my_role_requests, submit_role_request

router = APIRouter()


def to_out(row: RoleRequest) -> RoleRequestOut:
    return RoleRequestOut(
        id=row.id,
        requester_id=str(row.requester_id),
        role_id=row.role_id,
        source_ref=row.source_ref,
        reason=row.reason,
        requested_duration_hours=(
            row.requested_duration.total_seconds() / 3600 if row.requested_duration else None
        ),
        status=row.status,
        approver_id=str(row.approver_id) if row.approver_id else None,
        approved_at=row.approved_at,
        start_at=row.start_at,
        end_at=row.end_at,
        created_at=row.created_at,
    )


@router.post("", response_model=RoleRequestOut)
def post_role_request(
    body: SubmitRoleRequestIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        request = submit_role_request(
            db,
            requester_id=current_user.id,
            role_id=body.role_id,
            reason=body.reason,
            source_ref=body.source_ref,
            requested_duration=(
                timedelta(hours=body.requested_duration_hours)
                if body.requested_duration_hours
                else None
            ),
        )
    except RoleAdminError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    return to_out(request)


@router.get("/me", response_model=list[RoleRequestOut])
def get_my_role_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [to_out(r) for r in list_my_role_requests(db, current_user.id)]
