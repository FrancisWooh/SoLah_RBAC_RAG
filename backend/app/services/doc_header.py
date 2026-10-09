"""Read the access-control block a document carries at its top, e.g.

    Document ID: H01
    Department: HR
    Version: v1.0
    Classification: Internal
    Compartments: hr
    Allowed Roles: hr_manager

Used only for a NEW file that manifest.json does not list (library_sync turns the
result into a manifest entry). A header is a proposal by whoever wrote the file,
so anything missing, unknown or ambiguous is an error and the file is not indexed.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.services.doc_parser import parse_structured

HEADER_LINES = 30
_FIELD = re.compile(r"^[\s\-*•]*(?P<key>[A-Za-z][A-Za-z ]{1,30}?)\s*[:：]\s*(?P<value>.*?)\s*$")
_NONE = {"", "none", "-", "n/a", "无"}

# header label -> clearance (same scale as the manifest's "classification")
CLASSIFICATION_LEVELS = {
    "public": 1,
    "employee": 1,
    "public/employee": 1,
    "internal": 2,
    "confidential": 3,
    "secret": 4,
}


@dataclass
class HeaderAcl:
    allowed_roles: list[str] = field(default_factory=list)
    required_clearance: int = 0
    classification: str = ""
    compartments: list[str] = field(default_factory=list)
    department: str = ""
    version: str = ""
    doc_id: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _split(value: str) -> list[str]:
    return [p.strip().lower() for p in re.split(r"[;,，；、/]", value) if p.strip().lower() not in _NONE]


def read_header_acl(path: Path) -> HeaderAcl:
    fields: dict[str, str] = {}
    for text, _ in parse_structured(path)[:HEADER_LINES]:
        m = _FIELD.match(text)
        if m:
            fields.setdefault(m["key"].strip().lower(), m["value"])

    acl = HeaderAcl(
        department=fields.get("department", ""),
        version=fields.get("version", ""),
        doc_id=fields.get("document id", ""),
    )

    label = fields.get("classification", "").strip()
    level = CLASSIFICATION_LEVELS.get(label.lower())
    if level is None:
        acl.errors.append(f"Classification missing or unknown ({label!r}); expected one of Public/Internal/Confidential/Secret")
    else:
        acl.required_clearance, acl.classification = level, label

    if "compartments" not in fields:
        acl.errors.append("Compartments line missing (write 'Compartments: none' if there is none)")
    else:
        acl.compartments = _split(fields["compartments"])

    acl.allowed_roles = _split(fields.get("allowed roles", ""))  # empty -> default_roles()
    return acl


# Owning role(s) per department, taken from how manifest.json assigns them. Keys are
# the manifest "department" text and the top-level library folder. Deliberately the
# narrow owner role, never "employee" (except Public). "Projects" is absent on purpose:
# project documents belong to one project role, which cannot be guessed.
_DEPARTMENT_ROLES = {
    "public": ["employee"],
    "compliance": ["compliance_officer"],
    "risk & credit": ["risk_analyst"], "risk_credit": ["risk_analyst"],
    "card operations": ["card_ops"], "card_ops": ["card_ops"],
    "customer support": ["customer_support"], "customer_support": ["customer_support"],
    "finance": ["finance_analyst"],
    "hr": ["hr_manager"],
    "marketing": ["marketing_manager"],
    "sales & partnerships": ["account_manager"], "sales_partnerships": ["account_manager"],
    "engineering & security": ["engineer", "security_engineer"],
    "engineering_security": ["engineer", "security_engineer"],
    "legal": ["legal_counsel"],
    "executive": ["exec"],
}


def default_roles(department: str, folder: str) -> tuple[list[str], str]:
    """Allowed roles for a header with no Allowed Roles line: from the header's
    Department and the top-level folder. If both are known and disagree (a file
    dropped in the wrong folder) or neither is known, return ([], reason)."""
    by_dept = _DEPARTMENT_ROLES.get(department.strip().lower())
    by_folder = _DEPARTMENT_ROLES.get(folder.strip().lower())
    if by_dept and by_folder and by_dept != by_folder:
        return [], f"Department {department!r} contradicts folder {folder!r}; write Allowed Roles explicitly"
    roles = by_dept or by_folder
    if not roles:
        return [], f"no Allowed Roles line and department {department!r} / folder {folder!r} has no default role"
    return list(roles), ""
