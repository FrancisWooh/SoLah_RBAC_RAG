from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    username: str
    department: str | None
    clearance: int
    compartments: list[str]
    effective_roles: list[str]
