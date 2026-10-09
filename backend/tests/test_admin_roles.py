"""Scenario 3 (project join -> auto-grant -> query allowed; leave -> revoke
-> query denied again) plus the admin-only access gate, against the real
seeded demo data (alice/bob/admin + card_ops role)."""

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


def test_non_admin_is_blocked_from_admin_endpoints(client):
    bob_token = _login(client, "bob")

    assert client.get("/api/admin/roles", headers=_auth(bob_token)).status_code == 403
    assert (
        client.post(
            "/api/admin/roles/grant",
            json={"user_id": "x", "role_id": "platform_admin"},
            headers=_auth(bob_token),
        ).status_code
        == 403
    )


def test_admin_can_list_roles_and_users(client):
    admin_token = _login(client, "admin")

    roles_resp = client.get("/api/admin/roles", headers=_auth(admin_token))
    assert roles_resp.status_code == 200
    assert "card_ops" in {r["id"] for r in roles_resp.json()}

    users_resp = client.get("/api/admin/users", headers=_auth(admin_token))
    assert users_resp.status_code == 200
    assert "bob" in {u["username"] for u in users_resp.json()}


def _bob_id(client, bob_token: str) -> str:
    return client.get("/api/auth/me", headers=_auth(bob_token)).json()["user_id"]


def test_scenario_three_project_join_then_leave(client):
    admin_token = _login(client, "admin")
    bob_token = _login(client, "bob")
    bob_id = _bob_id(client, bob_token)

    before = client.post(
        "/api/query/text",
        json={"question": "企业卡额度可以申请提高吗？"},
        headers=_auth(bob_token),
    ).json()
    assert before["decision"] == "deny"

    join_resp = client.post(
        "/api/admin/projects/join",
        json={"project_id": "proj_card_program_test", "user_id": bob_id, "project_role": "card_ops"},
        headers=_auth(admin_token),
    )
    assert join_resp.status_code == 200

    during = client.post(
        "/api/query/text",
        json={"question": "企业卡额度可以申请提高吗？"},
        headers=_auth(bob_token),
    ).json()
    assert during["decision"] == "allow"
    assert "doc_card_limit_rules" in {c["doc_id"] for c in during["citations"]}

    leave_resp = client.post(
        "/api/admin/projects/leave",
        json={"project_id": "proj_card_program_test", "user_id": bob_id},
        headers=_auth(admin_token),
    )
    assert leave_resp.status_code == 200

    after = client.post(
        "/api/query/text",
        json={"question": "企业卡额度可以申请提高吗？"},
        headers=_auth(bob_token),
    ).json()
    assert after["decision"] == "deny"


def test_grant_and_revoke_role_directly(client):
    admin_token = _login(client, "admin")
    bob_token = _login(client, "bob")
    bob_id = _bob_id(client, bob_token)

    grant_resp = client.post(
        "/api/admin/roles/grant",
        json={"user_id": bob_id, "role_id": "card_ops", "source": "temporary"},
        headers=_auth(admin_token),
    )
    assert grant_resp.status_code == 200
    user_role_id = grant_resp.json()["id"]

    me = client.get("/api/auth/me", headers=_auth(bob_token)).json()
    assert "card_ops" in me["effective_roles"]

    revoke_resp = client.post(
        "/api/admin/roles/revoke",
        json={"user_role_id": user_role_id},
        headers=_auth(admin_token),
    )
    assert revoke_resp.status_code == 200

    me_after = client.get("/api/auth/me", headers=_auth(bob_token)).json()
    assert "card_ops" not in me_after["effective_roles"]


def test_grant_unknown_role_is_rejected(client):
    admin_token = _login(client, "admin")
    bob_token = _login(client, "bob")
    bob_id = _bob_id(client, bob_token)

    resp = client.post(
        "/api/admin/roles/grant",
        json={"user_id": bob_id, "role_id": "does_not_exist", "source": "temporary"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400
