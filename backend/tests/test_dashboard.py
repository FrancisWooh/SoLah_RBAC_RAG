import pytest

from app.core.db import get_db
from app.main import app
from app.models.data_source import DataSource


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


def test_dashboard_requires_admin(client):
    bob_token = _login(client, "bob")
    assert client.get("/api/admin/dashboard/stats", headers=_auth(bob_token)).status_code == 403


def test_dashboard_reflects_real_query_activity(client):
    admin_token = _login(client, "admin")
    alice_token = _login(client, "alice")

    # one allow, one deny, both real query_text endpoint calls
    client.post(
        "/api/query/text",
        json={"question": "KYC/AML 审核标准是什么？"},
        headers=_auth(alice_token),
    )
    client.post(
        "/api/query/text",
        json={"question": "客户投诉处理 SOP 是什么？"},
        headers=_auth(alice_token),
    )

    resp = client.get("/api/admin/dashboard/stats", headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_queries"] >= 2
    assert body["allow_count"] >= 1
    assert body["deny_count"] >= 1
    assert 0 <= body["deny_rate"] <= 1
    assert any(v["username"] == "alice" for v in body["recent_violations"])
    assert sum(p["count"] for p in body["query_volume_by_day"]) == body["total_queries"]


def test_dashboard_with_no_data_sources_reports_empty_not_fabricated(client, db_session):
    db_session.query(DataSource).delete()  # the dev DB may have registered department databases; rolled back after the test
    admin_token = _login(client, "admin")
    resp = client.get("/api/admin/dashboard/stats", headers=_auth(admin_token))
    assert resp.status_code == 200
    # honest reporting: no data_sources rows exist, so this must be empty
    # rather than some made-up "all healthy" placeholder
    assert resp.json()["sync_status_counts"] == {}


def test_dashboard_counts_registered_data_sources_by_sync_status(client, db_session):
    db_session.query(DataSource).delete()
    db_session.add_all([DataSource(name="a", sync_status="ok"), DataSource(name="b", sync_status="ok"),
                        DataSource(name="c", sync_status="error")])
    db_session.flush()
    admin_token = _login(client, "admin")
    resp = client.get("/api/admin/dashboard/stats", headers=_auth(admin_token))
    assert resp.json()["sync_status_counts"] == {"ok": 2, "error": 1}
