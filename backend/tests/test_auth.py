import uuid

import fakeredis
import pytest

from app.api import deps
from app.core.db import get_db
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.idp.group_mapping import MOCK_IDP_USERS

MOCK_IDP_BACKUP = {k: dict(v) for k, v in MOCK_IDP_USERS.items()}


@pytest.fixture()
def client(db_session, test_client):
    app.dependency_overrides[get_db] = lambda: db_session

    # deps.py and auth.py both do `from app.core.redis_client import redis_client`
    # and call it as a plain module global, not via Depends(), so the only way
    # to swap it for a test double is to patch that global in place.
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    deps.redis_client = fake_redis
    import app.api.auth as auth_module

    auth_module.redis_client = fake_redis

    yield test_client

    app.dependency_overrides.clear()
    # Restore mock IdP users so mutations from _seed_alice don't leak
    MOCK_IDP_USERS.clear()
    MOCK_IDP_USERS.update(MOCK_IDP_BACKUP)


def _seed_alice(db_session):
    # unique username so this never collides with rows committed outside the
    # test transaction (e.g. by seed_data.py)
    username = f"alice-{uuid.uuid4().hex[:8]}"
    db_session.merge(Role(id="compliance_officer", name="Compliance Officer"))
    db_session.merge(Role(id="employee", name="Employee"))
    user = User(username=username, clearance=2, compartments=["aml"])
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id="compliance_officer", source="permanent"))
    db_session.flush()
    # Register this randomised username with the mock IdP so login succeeds
    MOCK_IDP_USERS[username] = {
        "groups": ["aspire-all-employees", "aspire-compliance-team"],
        "email": f"{username}@aspire.demo",
        "department": "Compliance",
    }
    return user, username


def test_login_then_me_roundtrip(client, db_session):
    _, username = _seed_alice(db_session)

    login_resp = client.post("/api/auth/login", json={"username": username})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["username"] == username
    assert body["effective_roles"] == ["compliance_officer", "employee"]


def test_login_unknown_user_is_401(client, db_session):
    resp = client.post("/api/auth/login", json={"username": "ghost"})
    assert resp.status_code == 401


def test_me_without_token_is_rejected(client, db_session):
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_me_with_garbage_token_is_401(client, db_session):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
