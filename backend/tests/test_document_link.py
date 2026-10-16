"""GET /api/documents/{id}/link: the "view original" link must obey the same
RBAC as retrieval, answer 404 (never 403) so restricted documents' existence is
not confirmed, skip archived/non-file documents, and leave an audit trail.

Uses the seeded demo users/documents (henry = hr_manager, alice = compliance).
COS itself is faked: only the permission logic is under test.
"""

import pytest
from sqlalchemy import select

from app.core.db import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.services import cos_storage

HR_DOC = "doc_h01"  # hr/Leave_Policy_Admin_Guide.docx: hr_manager, clearance 2, compartment hr


@pytest.fixture()
def client(db_session, test_client, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(cos_storage, "is_configured", lambda: True)
    monkeypatch.setattr(
        cos_storage, "presigned_url", lambda key, filename: f"https://cos.example/{key}?sig=fake"
    )
    yield test_client
    app.dependency_overrides.clear()


def _token(client, username: str) -> dict:
    resp = client.post("/api/auth/login", json={"username": username})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _add_doc(db, doc_id, *, source_ref, status="active", roles=("employee",), clearance=1, compartments=()):
    db.add(
        Document(
            id=doc_id,
            source_type="nas",
            source_ref=source_ref,
            status=status,
            allowed_roles=list(roles),
            required_clearance=clearance,
            compartments=list(compartments),
            version="v1.0",
        )
    )
    db.flush()


def test_entitled_user_gets_a_link_to_the_right_object(client):
    resp = client.get(f"/api/documents/{HR_DOC}/link", headers=_token(client, "henry"))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["filename"] == "Leave_Policy_Admin_Guide.docx"
    assert body["url"].startswith("https://cos.example/") and "hr/Leave_Policy_Admin_Guide.docx" in body["url"]


def test_user_without_the_role_and_compartment_gets_404_not_403(client):
    resp = client.get(f"/api/documents/{HR_DOC}/link", headers=_token(client, "alice"))

    assert resp.status_code == 404
    assert "url" not in resp.text


def test_unknown_document_looks_identical_to_a_restricted_one(client):
    headers = _token(client, "alice")
    restricted = client.get(f"/api/documents/{HR_DOC}/link", headers=headers)
    unknown = client.get("/api/documents/doc_does_not_exist/link", headers=headers)

    assert restricted.status_code == unknown.status_code == 404
    assert restricted.json() == unknown.json()


def test_requires_login(client):
    assert client.get(f"/api/documents/{HR_DOC}/link").status_code in (401, 403)


def test_archived_document_is_not_linkable_even_if_permitted(client, db_session):
    _add_doc(db_session, "doc_t_archived", source_ref="/company_share/public/Old_Policy_v1.pdf", status="archived")

    resp = client.get("/api/documents/doc_t_archived/link", headers=_token(client, "alice"))

    assert resp.status_code == 404


def test_database_sourced_document_has_no_file(client, db_session):
    _add_doc(db_session, "doc_t_db", source_ref="db://hr/employees/42/jane")

    resp = client.get("/api/documents/doc_t_db/link", headers=_token(client, "alice"))

    assert resp.status_code == 404


def test_path_traversal_in_source_ref_is_refused():
    assert cos_storage.object_key("/company_share/../secrets/key.pem") is None
    assert cos_storage.object_key("/etc/passwd") is None
    assert cos_storage.object_key(None) is None
    assert cos_storage.object_key("/company_share/hr/a.docx").endswith("hr/a.docx")


def test_returns_503_when_cos_is_not_configured(client, monkeypatch):
    monkeypatch.setattr(cos_storage, "is_configured", lambda: False)

    resp = client.get(f"/api/documents/{HR_DOC}/link", headers=_token(client, "henry"))

    assert resp.status_code == 503


def test_allowed_and_denied_attempts_are_audited(client, db_session):
    client.get(f"/api/documents/{HR_DOC}/link", headers=_token(client, "henry"))
    client.get(f"/api/documents/{HR_DOC}/link", headers=_token(client, "alice"))

    rows = db_session.scalars(
        select(AuditLog).where(AuditLog.event_type == "doc_view").order_by(AuditLog.id.desc()).limit(2)
    ).all()
    denied, allowed = rows
    assert (allowed.decision, allowed.retrieved_doc_ids, allowed.blocked_doc_ids) == ("allow", [HR_DOC], [])
    assert (denied.decision, denied.retrieved_doc_ids, denied.blocked_doc_ids) == ("deny", [], [HR_DOC])
