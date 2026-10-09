import json
from pathlib import Path

# Default mapping: IdP group name -> local role_id.
# A real OIDC/SAML IdP would return group claims; these are the group
# names our mock IdP uses. Override the whole map via a JSON file at
# settings.idp_group_role_map_path if needed.
DEFAULT_GROUP_ROLE_MAP: dict[str, str] = {
    "aspire-all-employees": "employee",
    "aspire-compliance-team": "compliance_officer",
    "aspire-mlro": "mlro",
    "aspire-risk-credit": "risk_analyst",
    "aspire-card-ops": "card_ops",
    "aspire-customer-support": "customer_support",
    "aspire-finance-traders": "finance_analyst",
    "aspire-hr-managers": "hr_manager",
    "aspire-marketing": "marketing_manager",
    "aspire-sales-partnerships": "account_manager",
    "aspire-engineering": "engineer",
    "aspire-security": "security_engineer",
    "aspire-legal": "legal_counsel",
    "aspire-executive": "exec",
    "aspire-platform-ops": "platform_admin",
    "aspire-auditor": "auditor",
}

# Mock IdP directory: username -> {groups, email, department}.
# Derived from seed_data.py PERMANENT_ROLE_GRANTS so the mock IdP returns
# groups that map (via DEFAULT_GROUP_ROLE_MAP) to exactly the same roles
# each demo user already has. This keeps demo behaviour unchanged: after
# reconcile, the user's effective roles are the same as before.
# Tests mutate this dict at runtime to register randomised usernames.
MOCK_IDP_USERS: dict[str, dict] = {
    "alice":   {"groups": ["aspire-all-employees", "aspire-compliance-team"],
                "email": "alice@aspire.demo", "department": "Compliance"},
    "bob":     {"groups": ["aspire-all-employees", "aspire-engineering"],
                "email": "bob@aspire.demo", "department": "Engineering"},
    "admin":   {"groups": ["aspire-all-employees", "aspire-platform-ops"],
                "email": "admin@aspire.demo", "department": "Platform"},
    "auditor": {"groups": ["aspire-all-employees", "aspire-auditor"],
                "email": "auditor@aspire.demo", "department": "Internal Audit"},
    "carol":   {"groups": ["aspire-all-employees", "aspire-compliance-team", "aspire-mlro"],
                "email": "carol@aspire.demo", "department": "Compliance"},
    "dave":    {"groups": ["aspire-all-employees", "aspire-risk-credit"],
                "email": "dave@aspire.demo", "department": "Risk & Credit"},
    "erin":    {"groups": ["aspire-all-employees", "aspire-card-ops"],
                "email": "erin@aspire.demo", "department": "Card Operations"},
    "frank":   {"groups": ["aspire-all-employees", "aspire-customer-support"],
                "email": "frank@aspire.demo", "department": "Customer Support"},
    "gina":    {"groups": ["aspire-all-employees", "aspire-finance-traders"],
                "email": "gina@aspire.demo", "department": "Finance"},
    "henry":   {"groups": ["aspire-all-employees", "aspire-hr-managers"],
                "email": "henry@aspire.demo", "department": "HR"},
    "ivy":     {"groups": ["aspire-all-employees", "aspire-marketing"],
                "email": "ivy@aspire.demo", "department": "Marketing"},
    "jack":    {"groups": ["aspire-all-employees", "aspire-sales-partnerships"],
                "email": "jack@aspire.demo", "department": "Sales & Partnerships"},
    "kate":    {"groups": ["aspire-all-employees", "aspire-security"],
                "email": "kate@aspire.demo", "department": "Security"},
    "leo":     {"groups": ["aspire-all-employees", "aspire-legal"],
                "email": "leo@aspire.demo", "department": "Legal"},
    "vera":    {"groups": ["aspire-all-employees", "aspire-executive"],
                "email": "vera@aspire.demo", "department": "Executive"},
}


def load_group_role_map(path: str | None = None) -> dict[str, str]:
    """Load group->role mapping from a JSON file if *path* is given and
    the file exists; otherwise return the built-in default mapping."""
    if path:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text())
    return DEFAULT_GROUP_ROLE_MAP


def map_groups_to_roles(
    idp_groups: list[str], group_role_map: dict[str, str]
) -> dict[str, str]:
    """Map IdP groups to local role_ids.

    Returns ``{role_id: group_name}`` so the caller can set
    ``source_ref='idp:<group_name>'`` for each grant. Unknown groups are
    silently skipped (a group the IdP returns but we don't recognise is
    not an error -- it just doesn't map to a local role).
    """
    result: dict[str, str] = {}
    for group in idp_groups:
        role_id = group_role_map.get(group)
        if role_id and role_id not in result:
            result[role_id] = group
    return result
