"""Tests for the IdP login reconcile flow.

These tests exercise the full /api/auth/login -> IdP adapter -> group->role
mapping -> JIT provisioning -> three-way reconcile pipeline through the
HTTP layer, using the mock IdP provider.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.api import deps
from app.core.db import get_db
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.idp.factory import get_idp_adapter
from app.services.idp.group_mapping import MOCK_IDP_USERS

MOCK_IDP_BACKUP = {k: dict(v) for k, v in MOCK_IDP_USERS.items()}


@pytest.fixture()
def client(db_session, test_client):
    app.dependency_overrides[get_db] = lambda: db_session

    import fakeredis

    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    deps.redis_client = fake_redis
    import app.api.auth as auth_module

    auth_module.redis_client = fake_redis

    yield test_client

    app.dependency_overrides.clear()
    MOCK_IDP_USERS.clear()
    MOCK_IDP_USERS.update(MOCK_IDP_BACKUP)


def _register_mock_idp_user(username, groups, email=None, department=None):
    """Register a user in the mock IdP so authenticate() succeeds."""
    MOCK_IDP_USERS[username] = {
        "groups": groups,
        "email": email or f"{username}@aspire.demo",
        "department": department or "Test",
    }


def _ensure_roles(db_session, *role_ids):
    for rid in role_ids:
        db_session.merge(Role(id=rid, name=rid.replace("_", " ").title()))
    db_session.flush()


def _login(client, username):
    resp = client.post("/api/auth/login", json={"username": username})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. JIT provisioning: user not in DB, IdP knows them -> created on login
# ---------------------------------------------------------------------------
def test_login_creates_user_if_not_exists_jit_provisioning(client, db_session):
    username = f"newuser-{uuid.uuid4().hex[:8]}"
    _register_mock_idp_user(username, ["aspire-all-employees"])
    _ensure_roles(db_session, "employee")

    token = _login(client, username)

    # user was created in DB
    user = db_session.scalar(select(User).where(User.username == username))
    assert user is not None
    assert user.email == f"{username}@aspire.demo"
    assert user.department == "Test"

    # /me returns the mapped role
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert "employee" in me.json()["effective_roles"]


# ---------------------------------------------------------------------------
# 2. New groups granted on login
# ---------------------------------------------------------------------------
def test_login_reconciles_new_groups_granted(client, db_session):
    username = f"carol-{uuid.uuid4().hex[:8]}"
    _register_mock_idp_user(
        username,
        ["aspire-all-employees", "aspire-compliance-team"],
    )
    _ensure_roles(db_session, "employee", "compliance_officer")

    # user exists in DB but has no IdP-sourced roles yet
    user = User(username=username, clearance=2, compartments=["aml"])
    db_session.add(user)
    db_session.flush()

    _login(client, username)

    grants = db_session.scalars(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.source_ref.like("idp:%"),
            UserRole.status == "active",
        )
    ).all()
    grant_role_ids = {g.role_id for g in grants}
    assert grant_role_ids == {"employee", "compliance_officer"}


# ---------------------------------------------------------------------------
# 3. Removed groups revoked on second login
# ---------------------------------------------------------------------------
def test_login_reconciles_removed_groups_revoked(client, db_session):
    username = f"dave-{uuid.uuid4().hex[:8]}"
    _register_mock_idp_user(
        username,
        ["aspire-all-employees", "aspire-compliance-team"],
    )
    _ensure_roles(db_session, "employee", "compliance_officer")

    user = User(username=username, clearance=2, compartments=[])
    db_session.add(user)
    db_session.flush()

    # first login: both roles granted
    _login(client, username)

    grants_before = db_session.scalars(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.source_ref.like("idp:%"),
        )
    ).all()
    active_before = {g.role_id for g in grants_before if g.status == "active"}
    assert active_before == {"employee", "compliance_officer"}

    # second login: remove compliance group from IdP
    MOCK_IDP_USERS[username]["groups"] = ["aspire-all-employees"]
    _login(client, username)

    grants_after = db_session.scalars(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.source_ref.like("idp:%"),
        )
    ).all()
    active_after = {g.role_id for g in grants_after if g.status == "active"}
    revoked = {g.role_id for g in grants_after if g.status == "revoked"}
    assert active_after == {"employee"}
    assert revoked == {"compliance_officer"}


# ---------------------------------------------------------------------------
# 4. Directly-assigned roles (source_ref=None) survive reconcile
# ---------------------------------------------------------------------------
def test_idp_roles_do_not_interfere_with_directly_assigned_roles(client, db_session):
    username = f"frank-{uuid.uuid4().hex[:8]}"
    _register_mock_idp_user(username, ["aspire-all-employees"])
    _ensure_roles(db_session, "employee", "risk_analyst")

    user = User(username=username, clearance=2, compartments=[])
    db_session.add(user)
    db_session.flush()
    # directly-assigned role (source_ref=None) -- should be untouched
    db_session.add(UserRole(
        user_id=user.id, role_id="risk_analyst",
        source="permanent", source_ref=None, status="active",
    ))
    db_session.flush()

    _login(client, username)

    direct_grant = db_session.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == "risk_analyst",
            UserRole.source_ref.is_(None),
        )
    )
    assert direct_grant is not None
    assert direct_grant.status == "active"

    idp_grant = db_session.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == "employee",
            UserRole.source_ref.like("idp:%"),
        )
    )
    assert idp_grant is not None
    assert idp_grant.status == "active"


# ---------------------------------------------------------------------------
# 5. Project and temporary roles survive reconcile
# ---------------------------------------------------------------------------
def test_idp_roles_do_not_interfere_with_project_or_temporary_roles(client, db_session):
    username = f"gina-{uuid.uuid4().hex[:8]}"
    _register_mock_idp_user(username, ["aspire-all-employees"])
    _ensure_roles(db_session, "employee", "proj_merger")

    user = User(username=username, clearance=2, compartments=[])
    db_session.add(user)
    db_session.flush()
    # project-scoped role -- should be untouched by reconcile
    db_session.add(UserRole(
        user_id=user.id, role_id="proj_merger",
        source="project", source_ref="proj-123",
        end_at=datetime.utcnow() + timedelta(days=1),
        status="active",
    ))
    db_session.flush()

    _login(client, username)

    project_grant = db_session.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.source == "project",
            UserRole.source_ref == "proj-123",
        )
    )
    assert project_grant is not None
    assert project_grant.status == "active"


# ---------------------------------------------------------------------------
# 6. Unknown group in IdP is silently skipped
# ---------------------------------------------------------------------------
def test_unknown_group_in_mapping_is_skipped(client, db_session):
    username = f"ivy-{uuid.uuid4().hex[:8]}"
    _register_mock_idp_user(
        username,
        ["aspire-all-employees", "totally-unknown-group"],
    )
    _ensure_roles(db_session, "employee")

    _login(client, username)

    grants = db_session.scalars(
        select(UserRole).where(
            UserRole.source_ref.like("idp:%"),
            UserRole.status == "active",
        )
    ).all()
    assert all(g.role_id == "employee" for g in grants)
    assert len(grants) == 1


# ---------------------------------------------------------------------------
# 7. Unknown user (not in IdP) -> 401
# ---------------------------------------------------------------------------
def test_login_unknown_user_still_401(client, db_session):
    resp = client.post("/api/auth/login", json={"username": "ghost-nonexistent"})
    assert resp.status_code == 401
