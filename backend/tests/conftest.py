import os

# Tests exercise retrieval/RBAC, not generation: never call a real (slow, local-CPU) LLM.
os.environ["LLM_BACKEND"] = "mock"
os.environ["LIBRARY_SYNC_INTERVAL"] = "0"  # no background directory watcher in tests
os.environ["DB_SYNC_INTERVAL"] = "0"  # nor a database watcher
os.environ["IDP_PROVIDER"] = "mock"  # mock IdP for login reconcile tests

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import Base, engine
from app.core.redis_client import redis_client
from app.main import app
from app.models.role import Role
from app.models.user import User


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(scope="session")
def test_client():
    """One TestClient — and so one ASGI lifespan cycle — for the whole test
    session. app.mount("/mcp", ...) wires in FastMCP's StreamableHTTPSessionManager,
    whose .run() can only be entered once per process; the old pattern of
    each test file building its own `with TestClient(app) as c:` recreated
    the lifespan per test and broke on the second one with "run() can only
    be called once per instance". Every test-file `client` fixture now
    depends on this one instead of constructing its own TestClient.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_effective_roles_cache():
    """The effective-roles cache lives in the real Redis instance, not
    inside the Postgres test transaction, so a grant/revoke in one test can
    leak into the next test for up to its 30s TTL. Clear it before every
    test so each test starts from a cache miss, not a stale hit from
    whatever ran just before it."""
    for key in redis_client.scan_iter("effective_roles:*"):
        redis_client.delete(key)
    yield


@pytest.fixture()
def db_session():
    """One real Postgres transaction per test, rolled back at the end.

    ARRAY/JSONB columns are Postgres-specific, so tests run against the same
    Postgres container the app uses rather than an in-memory sqlite db.

    join_transaction_mode="create_savepoint" is load-bearing: several
    endpoints under test (query, role grant/revoke, project join/leave) call
    db.commit() themselves. Without this, that commit would go through to
    the *outer* transaction/connection and permanently write to the real dev
    database no matter what the fixture does afterwards — a plain
    `sessionmaker(bind=connection)` does NOT contain commit() the way you'd
    expect. This mode makes commit() only release/recreate a SAVEPOINT, so
    the final rollback() below genuinely undoes everything.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def make_user(db_session):
    """username is suffixed with a random id so tests never collide with
    rows committed outside the test transaction, e.g. by seed_data.py."""

    def _make_user(username: str, clearance: int = 1, compartments: list[str] | None = None) -> User:
        unique_username = f"{username}-{uuid.uuid4().hex[:8]}"
        user = User(username=unique_username, clearance=clearance, compartments=compartments or [])
        db_session.add(user)
        db_session.flush()
        return user

    return _make_user


@pytest.fixture()
def make_role(db_session):
    def _make_role(role_id: str, is_permanent: bool = True) -> Role:
        role = Role(id=role_id, name=role_id, is_permanent=is_permanent)
        db_session.merge(role)
        db_session.flush()
        return role

    return _make_role
