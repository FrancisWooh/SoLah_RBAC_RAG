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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_submit_then_approve_grants_the_role_and_it_expires(client):
    bob_token = _login(client, "bob")
    admin_token = _login(client, "admin")

    submit_resp = client.post(
        "/api/role-requests",
        json={"role_id": "card_ops", "reason": "需要处理提额审核", "requested_duration_hours": 2},
        headers=_auth(bob_token),
    )
    assert submit_resp.status_code == 200
    request_id = submit_resp.json()["id"]
    assert submit_resp.json()["status"] == "pending"

    before = client.post(
        "/api/query/text",
        json={"question": "企业卡额度可以申请提高吗？"},
        headers=_auth(bob_token),
    ).json()
    assert before["decision"] == "deny"

    approve_resp = client.post(
        f"/api/admin/role-requests/{request_id}/approve", headers=_auth(admin_token)
    )
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "approved"
    assert approved["end_at"] is not None

    after = client.post(
        "/api/query/text",
        json={"question": "企业卡额度可以申请提高吗？"},
        headers=_auth(bob_token),
    ).json()
    assert after["decision"] == "allow"


def test_reject_does_not_grant_the_role(client):
    bob_token = _login(client, "bob")
    admin_token = _login(client, "admin")

    submit_resp = client.post(
        "/api/role-requests",
        json={"role_id": "card_ops", "reason": "test"},
        headers=_auth(bob_token),
    )
    request_id = submit_resp.json()["id"]

    reject_resp = client.post(
        f"/api/admin/role-requests/{request_id}/reject", headers=_auth(admin_token)
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    after = client.post(
        "/api/query/text",
        json={"question": "企业卡额度可以申请提高吗？"},
        headers=_auth(bob_token),
    ).json()
    assert after["decision"] == "deny"


def test_cannot_approve_twice(client):
    bob_token = _login(client, "bob")
    admin_token = _login(client, "admin")

    request_id = client.post(
        "/api/role-requests",
        json={"role_id": "card_ops", "reason": "test"},
        headers=_auth(bob_token),
    ).json()["id"]

    first = client.post(f"/api/admin/role-requests/{request_id}/approve", headers=_auth(admin_token))
    assert first.status_code == 200

    second = client.post(f"/api/admin/role-requests/{request_id}/approve", headers=_auth(admin_token))
    assert second.status_code == 400


def test_submitting_for_unknown_role_is_rejected(client):
    bob_token = _login(client, "bob")
    resp = client.post(
        "/api/role-requests",
        json={"role_id": "does_not_exist", "reason": "test"},
        headers=_auth(bob_token),
    )
    assert resp.status_code == 400


def test_my_requests_only_shows_own_requests(client):
    bob_token = _login(client, "bob")
    alice_token = _login(client, "alice")

    client.post(
        "/api/role-requests",
        json={"role_id": "card_ops", "reason": "bob's request"},
        headers=_auth(bob_token),
    )

    alice_list = client.get("/api/role-requests/me", headers=_auth(alice_token)).json()
    assert all(r["reason"] != "bob's request" for r in alice_list)

    bob_list = client.get("/api/role-requests/me", headers=_auth(bob_token)).json()
    assert any(r["reason"] == "bob's request" for r in bob_list)


def test_admin_role_requests_list_requires_admin(client):
    bob_token = _login(client, "bob")
    resp = client.get("/api/admin/role-requests", headers=_auth(bob_token))
    assert resp.status_code == 403
