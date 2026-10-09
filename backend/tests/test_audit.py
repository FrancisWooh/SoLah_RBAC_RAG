"""Hash-chain and audit API tests. Uses db_session (rolled back after each
test) for everything, including the tamper test — never mutates the real
audit_logs table."""

import pytest
from sqlalchemy import select

from app.core.db import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.services.audit import append_audit_log, verify_audit_chain


@pytest.fixture()
def client(db_session, test_client):
    app.dependency_overrides[get_db] = lambda: db_session
    yield test_client
    app.dependency_overrides.clear()


def _login(client, username: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_chain_links_to_whatever_was_already_there(db_session):
    before = verify_audit_chain(db_session)
    assert before.ok

    append_audit_log(db_session, event_type="query", decision="allow")
    append_audit_log(db_session, event_type="query", decision="deny", deny_reason="x")
    db_session.flush()

    after = verify_audit_chain(db_session)
    assert after.ok
    assert after.rows_checked == before.rows_checked + 2


def test_tampering_with_a_row_is_detected(db_session):
    append_audit_log(db_session, event_type="query", decision="allow", query_text="original")
    db_session.flush()

    assert verify_audit_chain(db_session).ok

    tampered = db_session.scalars(
        select(AuditLog).where(AuditLog.query_text == "original")
    ).one()
    tampered.query_text = "tampered"
    db_session.flush()

    result = verify_audit_chain(db_session)
    assert not result.ok
    assert result.broken_at_id == tampered.id


def test_deleting_a_row_breaks_the_chain(db_session):
    """Chain linkage (not just per-row content) is what's actually checked:
    a row's prev_hash must match the PRECEDING row's record_hash. Deleting a
    row (or reordering, which has the same effect) leaves the next row's
    prev_hash pointing at a record_hash that's no longer the one before it."""
    append_audit_log(db_session, event_type="query", decision="allow", latency_ms=1)
    append_audit_log(db_session, event_type="query", decision="allow", latency_ms=2)
    append_audit_log(db_session, event_type="query", decision="allow", latency_ms=3)
    db_session.flush()

    assert verify_audit_chain(db_session).ok

    middle = db_session.scalars(
        select(AuditLog).where(AuditLog.latency_ms == 2)
    ).one()
    db_session.delete(middle)
    db_session.flush()

    result = verify_audit_chain(db_session)
    assert not result.ok
    assert result.reason == "prev_hash 与前一条记录的 record_hash 不匹配"


def test_audit_log_endpoints_require_admin(client):
    bob_token = _login(client, "bob")
    assert client.get("/api/admin/audit/logs", headers=_auth(bob_token)).status_code == 403
    assert client.get("/api/admin/audit/verify", headers=_auth(bob_token)).status_code == 403
    assert client.get("/api/admin/audit/export", headers=_auth(bob_token)).status_code == 403


def test_admin_can_list_filter_and_export_logs(client):
    admin_token = _login(client, "admin")
    alice_token = _login(client, "alice")

    client.post(
        "/api/query/text",
        json={"question": "KYC/AML 审核标准是什么？"},
        headers=_auth(alice_token),
    )

    list_resp = client.get(
        "/api/admin/audit/logs?event_type=query&decision=allow&limit=5",
        headers=_auth(admin_token),
    )
    assert list_resp.status_code == 200
    rows = list_resp.json()
    assert len(rows) > 0
    assert all(r["event_type"] == "query" and r["decision"] == "allow" for r in rows)

    detail_resp = client.get(f"/api/admin/audit/logs/{rows[0]['id']}", headers=_auth(admin_token))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == rows[0]["id"]

    missing_resp = client.get("/api/admin/audit/logs/99999999", headers=_auth(admin_token))
    assert missing_resp.status_code == 404

    export_resp = client.get("/api/admin/audit/export?format=csv", headers=_auth(admin_token))
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    assert "attachment" in export_resp.headers["content-disposition"]


def test_verify_endpoint_reports_ok_for_untampered_chain(client):
    admin_token = _login(client, "admin")
    resp = client.get("/api/admin/audit/verify", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# --- blocked_doc_ids: which restricted document a denied user was after -------


def test_rows_without_blocked_doc_ids_keep_the_same_hash_as_before_the_field_existed(db_session):
    from app.services.audit import GENESIS_HASH, _compute_record_hash

    fields = dict(event_type="query", decision="deny", query_text="q", effective_roles=[], retrieved_doc_ids=[])
    legacy = _compute_record_hash(GENESIS_HASH, fields)
    assert _compute_record_hash(GENESIS_HASH, {**fields, "blocked_doc_ids": None}) == legacy
    assert _compute_record_hash(GENESIS_HASH, {**fields, "blocked_doc_ids": []}) == legacy


def test_blocked_doc_ids_are_covered_by_the_chain(db_session):
    row = append_audit_log(db_session, event_type="query", decision="deny", blocked_doc_ids=["doc_h02"])
    db_session.flush()
    assert verify_audit_chain(db_session).ok

    row.blocked_doc_ids = ["doc_x01"]  # rewrite which document was targeted
    db_session.flush()
    result = verify_audit_chain(db_session)
    assert not result.ok and result.broken_at_id == row.id

    row.blocked_doc_ids = []  # or erase it
    db_session.flush()
    assert not verify_audit_chain(db_session).ok


def test_denied_query_audits_the_blocked_document_but_never_tells_the_user(client, db_session, monkeypatch):
    from app.services import query_service

    monkeypatch.setattr(query_service, "get_llm", lambda: pytest.fail("no LLM on deny"))
    token = _login(client, "alice")

    resp = client.post("/api/query/text", json={"question": "Compensation band for grade G5"}, headers=_auth(token))

    body = resp.json()
    assert body["decision"] == "deny"
    assert "doc_h02" not in resp.text and "blocked" not in resp.text  # nothing about the target leaks
    row = db_session.scalars(
        select(AuditLog).where(AuditLog.query_text == "Compensation band for grade G5", AuditLog.decision == "deny")
        .order_by(AuditLog.id.desc())
    ).first()
    assert row.blocked_doc_ids == ["doc_h02"]
    assert verify_audit_chain(db_session).ok


def test_allowed_query_has_no_blocked_docs(client, db_session):
    token = _login(client, "alice")
    client.post("/api/query/text", json={"question": "KYC/AML 审核标准是什么？"}, headers=_auth(token))
    row = db_session.scalars(
        select(AuditLog).where(AuditLog.query_text == "KYC/AML 审核标准是什么？", AuditLog.decision == "allow")
        .order_by(AuditLog.id.desc())
    ).first()
    assert not row.blocked_doc_ids


def test_several_appends_in_one_transaction_form_one_chain_even_with_autoflush_off(db_session):
    # SessionLocal runs with autoflush=False; production code that appends more than one row
    # per transaction (seeding, multi-grant operations) must still get a single chain.
    from sqlalchemy.orm import Session

    session = Session(bind=db_session.get_bind(), autoflush=False, join_transaction_mode="create_savepoint")
    try:
        first = append_audit_log(session, event_type="query", decision="allow")
        second = append_audit_log(session, event_type="query", decision="deny")
        third = append_audit_log(session, event_type="query", decision="allow")
        assert second.prev_hash == first.record_hash
        assert third.prev_hash == second.record_hash
        session.flush()
        assert verify_audit_chain(session).ok
    finally:
        session.rollback()
        session.close()
