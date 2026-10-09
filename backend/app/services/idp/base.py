from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class IdPUserInfo:
    username: str
    email: str | None = None
    department: str | None = None
    idp_groups: list[str] = field(default_factory=list)


class IdPAdapter(Protocol):
    def authenticate(self, username: str) -> IdPUserInfo:
        """Given the login identity (username for mock; would be an auth
        code / token for real OIDC/SAML), return user info including the
        IdP groups the user belongs to. Raises IdPAuthenticationError if
        the user is not known to the IdP."""
        ...


class IdPAuthenticationError(Exception):
    """Raised when the IdP does not recognise the user."""
    pass
