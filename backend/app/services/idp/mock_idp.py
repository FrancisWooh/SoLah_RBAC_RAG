from app.services.idp.base import IdPAuthenticationError, IdPUserInfo
from app.services.idp.group_mapping import MOCK_IDP_USERS


class MockIdPAdapter:
    """Simulates what a real OIDC/SAML IdP would return on login.

    The ``authenticate`` call is the IdP callback equivalent: given the
    username (the credential for the mock), return the user's info
    including their IdP group memberships. In a real adapter this would
    exchange an authorisation code for tokens and decode the ID token.
    """

    def authenticate(self, username: str) -> IdPUserInfo:
        entry = MOCK_IDP_USERS.get(username)
        if entry is None:
            raise IdPAuthenticationError(f"IdP does not recognise user: {username}")
        return IdPUserInfo(
            username=username,
            email=entry["email"],
            department=entry["department"],
            idp_groups=entry["groups"],
        )
