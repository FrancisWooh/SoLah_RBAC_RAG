"""Reset the database to a known demo state.

Covers the data needed for demo scenarios 1/2 (normal query, denied query)
straight away. Scenario 3 (temporary role via project membership) is granted
live during the demo through the admin API, not pre-seeded here, so the
grant/expire behaviour is actually demonstrated rather than already baked in.

Usage: python seed_data.py  (or: docker compose exec backend python seed_data.py)
"""

import json
from pathlib import Path

from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.models.document import Document
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

def _user(username, dept, clearance, compartments):
    return dict(username=username, email=f"{username}@aspire.demo", department=dept,
                clearance=clearance, compartments=compartments)


# see requirement/doc_permission_matrix.md for the persona/document matrix
USERS = [
    _user("alice", "Compliance", 2, ["aml"]),
    _user("bob", "Engineering", 2, []),  # 2 (was 1) so scenario 3 can read the clearance-2 merger docs
    _user("admin", "Platform", 4, ["aml", "finance"]),
    _user("auditor", "Internal Audit", 1, []),  # service identity for the WorkBuddy MCP connection
    _user("carol", "Compliance", 3, ["aml"]),
    _user("dave", "Risk & Credit", 3, ["credit"]),
    _user("erin", "Card Operations", 2, []),
    _user("frank", "Customer Support", 1, []),
    _user("gina", "Finance", 3, ["finance"]),
    _user("henry", "HR", 3, ["hr"]),
    _user("ivy", "Marketing", 2, []),
    _user("jack", "Sales & Partnerships", 2, []),
    _user("kate", "Security", 3, ["security"]),
    _user("leo", "Legal", 3, ["legal"]),
    _user("vera", "Executive", 4, ["board", "hr", "finance"]),
]

_PERM = [
    ("employee", "Employee"), ("compliance_officer", "Compliance Officer"), ("mlro", "MLRO"),
    ("risk_analyst", "Risk Analyst"), ("customer_support", "Customer Support"),
    ("finance_analyst", "Finance Analyst"), ("hr_manager", "HR Manager"),
    ("marketing_manager", "Marketing Manager"), ("account_manager", "Account Manager"),
    ("engineer", "Engineer"), ("security_engineer", "Security Engineer"),
    ("legal_counsel", "Legal Counsel"), ("exec", "Executive"), ("platform_admin", "Platform Admin"),
    ("auditor", "Auditor (read-only audit access for MCP agents)"),
]
# temporary/project roles: granted via approval or project membership, expire
_TEMP = [
    ("card_ops", "Card Operations"), ("proj_merger", "Project Merger"),
    ("proj_mas_audit", "Project MAS Audit"), ("proj_card_launch_vn", "Project Card Launch VN"),
    ("proj_aml_upgrade", "Project AML Upgrade"),
]
ROLES = [dict(id=i, name=n, is_permanent=True) for i, n in _PERM] + [
    dict(id=i, name=n, is_permanent=False, approver_role="platform_admin") for i, n in _TEMP
]

# username -> permanent roles
PERMANENT_ROLE_GRANTS = {
    "alice": ["employee", "compliance_officer"],
    "bob": ["employee", "engineer"],
    "admin": ["employee", "platform_admin"],
    "auditor": ["employee", "auditor"],
    "carol": ["employee", "compliance_officer", "mlro"],
    "dave": ["employee", "risk_analyst"],
    "erin": ["employee", "card_ops"],
    "frank": ["employee", "customer_support"],
    "gina": ["employee", "finance_analyst"],
    "henry": ["employee", "hr_manager"],
    "ivy": ["employee", "marketing_manager"],
    "jack": ["employee", "account_manager"],
    "kate": ["employee", "security_engineer"],
    "leo": ["employee", "legal_counsel"],
    "vera": ["employee", "exec"],
}

# manifest id -> legacy document id (existing tests/demo scripts reference these)
_LEGACY_IDS = {
    "C01": "doc_kyc_aml_policy", "C02": "doc_casa_kyc_requirements",
    "S01": "doc_customer_support_sop", "K01": "doc_card_limit_rules",
}


def manifest_doc_id(manifest_id: str) -> str:
    return _LEGACY_IDS.get(manifest_id, f"doc_{manifest_id.lower()}")


def _load_documents() -> list[dict]:
    """Document metadata comes from the document library's manifest.json
    (data/, generated alongside the files)."""
    manifest = Path(settings.data_dir) / "manifest.json"
    if not manifest.exists():
        raise SystemExit(f"manifest not found: {manifest} (set DATA_DIR to the document library root)")
    return [
        dict(id=manifest_doc_id(m["id"]), source_type=m["source_type"], source_ref=m["source_ref"],
             version=m["version"], status=m["status"], allowed_roles=m["allowed_roles"],
             required_clearance=m["required_clearance"], compartments=m["compartments"],
             content_hash=m["content_hash"])
        for m in json.loads(manifest.read_text())
    ]


def reset_and_seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        # delete in FK-safe order; skip tables that aren't populated by seed
        db.query(UserRole).delete()
        db.query(Document).delete()
        db.query(User).delete()
        db.query(Role).delete()
        db.flush()

        roles_by_id = {}
        for r in ROLES:
            role = Role(**r)
            db.add(role)
            roles_by_id[role.id] = role
        db.flush()

        users_by_username = {}
        for u in USERS:
            user = User(**u)
            db.add(user)
            users_by_username[user.username] = user
        db.flush()

        for username, role_ids in PERMANENT_ROLE_GRANTS.items():
            user = users_by_username[username]
            for role_id in role_ids:
                db.add(UserRole(user_id=user.id, role_id=role_id, source="permanent", end_at=None))

        documents = _load_documents()
        for d in documents:
            db.add(Document(**d))

        db.commit()
        print(f"Seeded {len(USERS)} users, {len(ROLES)} roles, {len(documents)} documents.")
    finally:
        db.close()


if __name__ == "__main__":
    reset_and_seed()
