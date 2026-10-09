"""RBAC matrix check against the REAL seeded document library (data/ +
seed_data.py + seed_vectorstore.py, local embedder). For every demo persona
and a spread of questions, every cited document must be one the persona is
entitled to per requirement/doc_permission_matrix.md — the expected set is
computed here from manifest.json + seed_data.py, independently of the app's
filtering code — and archived versions must never be cited.

Depends on the library having been seeded; see test_query.py's note.
"""

import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.main import app
from app.models.document import Document
from seed_data import PERMANENT_ROLE_GRANTS, USERS, manifest_doc_id

MANIFEST = {manifest_doc_id(m["id"]): m for m in json.loads((Path(settings.data_dir) / "manifest.json").read_text())}
PERSONAS = {u["username"]: u for u in USERS}

QUESTIONS = [
    "KYC/AML 审核标准是什么？",
    "年假政策有多少天？",
    "What is the SEV1 incident acknowledgement time?",
    "STR filing guideline deadline",
    "Compensation band for grade G5",
    "公司第三季度收入是多少",
    "What is the SWIFT outgoing transfer fee?",
    "客户投诉处理时效要求",
    "Valuation range for the PayNest acquisition",
    "Board resolution on the FY2027 budget",
]


def _db_records() -> dict[str, dict]:
    """Records synced from the department databases (documents.source_type == 'db'), same shape as a manifest entry."""
    with SessionLocal() as db:
        return {
            d.id: dict(status=d.status, allowed_roles=d.allowed_roles, required_clearance=d.required_clearance,
                       compartments=d.compartments)
            for d in db.query(Document).filter(Document.source_type == "db")
        }


def _permitted_docs(username: str) -> set[str]:
    p = PERSONAS[username]
    roles = set(PERMANENT_ROLE_GRANTS[username])
    return {
        doc_id
        for doc_id, m in {**MANIFEST, **_db_records()}.items()
        if m["status"] == "active"
        and roles & set(m["allowed_roles"])
        and m["required_clearance"] <= p["clearance"]
        and set(m["compartments"]) <= set(p["compartments"])
    }


@pytest.fixture()
def client(db_session, test_client):
    app.dependency_overrides[get_db] = lambda: db_session
    yield test_client
    app.dependency_overrides.clear()


def _ask(client, username: str, question: str) -> dict:
    token = client.post("/api/auth/login", json={"username": username}).json()["access_token"]
    resp = client.post("/api/query/text", json={"question": question}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.parametrize("username", sorted(PERSONAS))
def test_every_citation_is_permitted_and_active(client, username):
    permitted = _permitted_docs(username)
    for question in QUESTIONS:
        cited = {c["doc_id"] for c in _ask(client, username, question)["citations"]}
        assert cited <= permitted, f"{username} was shown {cited - permitted} for {question!r}"


def test_archived_policy_version_is_never_cited(client):
    cited = {c["doc_id"] for c in _ask(client, "alice", "KYC/AML 审核标准是什么？")["citations"]}
    assert "doc_kyc_aml_policy" in cited
    assert "doc_c01a" not in cited


def test_clearance_gate_alice_denied_but_carol_allowed_for_str_guideline(client):
    q = "STR filing guideline: how soon must a suspicious transaction report be filed?"
    assert "doc_c04" not in {c["doc_id"] for c in _ask(client, "alice", q)["citations"]}
    assert "doc_c04" in {c["doc_id"] for c in _ask(client, "carol", q)["citations"]}


def test_role_gate_alice_denied_leave_policy_but_henry_allowed(client):
    q = "年假政策有多少天？"
    assert _ask(client, "alice", q)["decision"] == "deny"
    assert "doc_h01" in {c["doc_id"] for c in _ask(client, "henry", q)["citations"]}


def test_admin_has_no_business_content_access(client):
    body = _ask(client, "admin", "Compensation band for grade G5")
    assert "doc_h02" not in {c["doc_id"] for c in body["citations"]}
