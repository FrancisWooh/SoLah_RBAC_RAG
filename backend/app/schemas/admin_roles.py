from datetime import datetime

from pydantic import BaseModel


class RoleOut(BaseModel):
    id: str
    name: str
    description: str | None
    is_permanent: bool
    approver_role: str | None


class UserOut(BaseModel):
    id: str
    username: str
    department: str | None
    clearance: int
    compartments: list[str]


class UserRoleOut(BaseModel):
    id: int
    user_id: str
    role_id: str
    source: str
    source_ref: str | None
    start_at: datetime
    end_at: datetime | None
    status: str


class GrantRoleRequest(BaseModel):
    user_id: str
    role_id: str
    source: str = "temporary"  # 'permanent' | 'project' | 'temporary'
    source_ref: str | None = None
    end_at: datetime | None = None


class RevokeRoleRequest(BaseModel):
    user_role_id: int


class ProjectJoinRequest(BaseModel):
    project_id: str
    user_id: str
    project_role: str
    project_end_at: datetime | None = None


class ProjectLeaveRequest(BaseModel):
    project_id: str
    user_id: str
