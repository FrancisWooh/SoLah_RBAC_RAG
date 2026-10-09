from functools import lru_cache

from app.core.config import settings
from app.services.idp.base import IdPAdapter


@lru_cache
def get_idp_adapter() -> IdPAdapter:
    """Return the configured IdP adapter. Same factory pattern as
    get_llm(), get_embedder(), get_vector_store().

    ``settings.idp_provider`` selects the backend:
      - ``mock`` (default): MockIdPAdapter, reads MOCK_IDP_USERS
      - ``oidc`` / ``saml``: reserved for future real adapters
    """
    if settings.idp_provider == "oidc":
        # Future: from app.services.idp.oidc_idp import OIDCIdPAdapter
        # return OIDCIdPAdapter()
        raise NotImplementedError("OIDC IdP not yet implemented")

    if settings.idp_provider == "saml":
        # Future: from app.services.idp.saml_idp import SAMLIdPAdapter
        # return SAMLIdPAdapter()
        raise NotImplementedError("SAML IdP not yet implemented")

    from app.services.idp.mock_idp import MockIdPAdapter

    return MockIdPAdapter()
