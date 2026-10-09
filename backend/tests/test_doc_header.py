from pathlib import Path

import pytest

from app.services.doc_header import default_roles, read_header_acl


def _md(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "doc.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_complete_header(tmp_path):
    acl = read_header_acl(_md(tmp_path, (
        "# Leave Policy\n\n- Document ID: H09\n- Department: HR\n- Version: v2.0\n"
        "- Classification: Confidential\n- Compartments: hr; board\n- Allowed Roles: hr_manager, exec\n"
    )))
    assert acl.ok
    assert (acl.required_clearance, acl.compartments, acl.allowed_roles) == (3, ["hr", "board"], ["hr_manager", "exec"])
    assert (acl.doc_id, acl.department, acl.version) == ("H09", "HR", "v2.0")


def test_compartments_none_is_empty(tmp_path):
    acl = read_header_acl(_md(tmp_path, "Classification: Public\nCompartments: none\nAllowed Roles: employee\n"))
    assert acl.ok and acl.compartments == [] and acl.required_clearance == 1


@pytest.mark.parametrize(
    "body",
    [
        "Compartments: none\nAllowed Roles: employee\n",  # no classification
        "Classification: Internal\nAllowed Roles: employee\n",  # no compartments line
        "Classification: Top Secret!\nCompartments: none\nAllowed Roles: employee\n",  # unknown label
        "Just some text with no header at all\n",
    ],
)
def test_incomplete_header_is_rejected(tmp_path, body):
    assert not read_header_acl(_md(tmp_path, body)).ok


def test_missing_allowed_roles_is_left_empty_for_the_caller_to_default(tmp_path):
    acl = read_header_acl(_md(tmp_path, "Department: HR\nClassification: Internal\nCompartments: hr\n"))
    assert acl.ok and acl.allowed_roles == []


@pytest.mark.parametrize(
    "department,folder,roles",
    [
        ("HR", "hr", ["hr_manager"]),
        ("Finance", "finance", ["finance_analyst"]),
        ("People and Culture", "public", ["employee"]),  # unknown label, folder decides
        ("", "legal", ["legal_counsel"]),
        ("Engineering & Security", "engineering_security", ["engineer", "security_engineer"]),
    ],
)
def test_default_roles(department, folder, roles):
    assert default_roles(department, folder) == (roles, "")


@pytest.mark.parametrize("department,folder", [("HR", "public"), ("", "projects"), ("Unknown Dept", "misc")])
def test_default_roles_refuses_conflict_or_unknown(department, folder):
    roles, why = default_roles(department, folder)
    assert roles == [] and why
