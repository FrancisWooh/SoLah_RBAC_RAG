"""End-to-end tests for demo scenarios 1 and 2, against the REAL seeded demo
data (seed_data.py's alice/bob + seed_vectorstore.py's 4 documents in the
real "knowledge_chunks" Qdrant collection) and the real redis cache — only
Postgres writes are wrapped in a rolled-back transaction so the real
audit_logs table isn't polluted by test runs.

If this file starts failing, first check whether seed_data.py /
seed_vectorstore.py have been re-run with different content — these tests
depend on that fixture data, not synthetic data of their own.
"""

import pytest

from app.core.db import get_db
from app.main import app


@pytest.fixture()
def client(db_session, test_client):
    app.dependency_overrides[get_db] = lambda: db_session
    yield test_client
    app.dependency_overrides.clear()


def _login(client, username: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _ask(client, token: str, question: str):
    return client.post(
        "/api/query/text",
        json={"question": question},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_scenario_one_alice_can_see_her_own_domain(client):
    token = _login(client, "alice")

    resp = _ask(client, token, "KYC/AML 审核标准是什么？")

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "allow"
    assert body["deny_reason"] is None
    assert "doc_kyc_aml_policy" in {c["doc_id"] for c in body["citations"]}


def test_scenario_two_alice_is_denied_outside_her_domain(client):
    token = _login(client, "alice")

    resp = _ask(client, token, "客户投诉处理 SOP 是什么？")

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "deny"
    assert body["deny_reason"]
    assert body["citations"] == []
    assert body["answer"] is None


def test_unrelated_question_is_allow_with_no_citations(client):
    token = _login(client, "alice")

    resp = _ask(client, token, "今天天气怎么样？")

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "allow"
    assert body["citations"] == []


def test_bob_never_sees_restricted_compliance_documents(client):
    # The library also holds an employee-visible compliance training deck, so a
    # KYC question from bob may legitimately be answered from that public
    # material. What must never happen is a restricted compliance document
    # (KYC/AML policy v3 or archived v2, CASA KYC, sanctions procedure, STR
    # guideline) being cited to him.
    token = _login(client, "bob")

    resp = _ask(client, token, "KYC/AML 审核标准是什么？")

    assert resp.status_code == 200
    cited = {c["doc_id"] for c in resp.json()["citations"]}
    restricted = {"doc_kyc_aml_policy", "doc_c01a", "doc_casa_kyc_requirements", "doc_c03", "doc_c04"}
    assert not cited & restricted


def test_query_requires_auth(client):
    resp = client.post("/api/query/text", json={"question": "anything"})
    assert resp.status_code in (401, 403)


def test_audit_log_row_written_for_each_query(client, db_session):
    from sqlalchemy import select

    from app.models.audit_log import AuditLog
    from app.models.user import User

    token = _login(client, "alice")
    _ask(client, token, "KYC/AML 审核标准是什么？")

    alice_id = db_session.scalar(select(User.id).where(User.username == "alice"))
    rows = db_session.scalars(
        select(AuditLog)
        .where(AuditLog.query_text == "KYC/AML 审核标准是什么？", AuditLog.user_id == alice_id)
        .order_by(AuditLog.id)
    ).all()
    assert len(rows) >= 1
    latest = rows[-1]
    assert latest.event_type == "query"
    assert latest.decision == "allow"
    assert "doc_kyc_aml_policy" in latest.retrieved_doc_ids
