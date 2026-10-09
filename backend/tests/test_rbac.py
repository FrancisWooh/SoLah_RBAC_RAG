from datetime import datetime, timedelta

from app.models.user_role import UserRole
from app.services.rbac import get_effective_roles


def _grant(db_session, user, role_id, source, end_at=None, status="active"):
    ur = UserRole(
        user_id=user.id,
        role_id=role_id,
        source=source,
        end_at=end_at,
        status=status,
    )
    db_session.add(ur)
    db_session.flush()
    return ur


def test_permanent_role_always_included(db_session, make_user, make_role):
    make_role("finance_analyst")
    user = make_user("alice")
    _grant(db_session, user, "finance_analyst", source="permanent", end_at=None)

    assert get_effective_roles(db_session, user.id) == {"finance_analyst"}


def test_active_temporary_role_included_before_expiry(db_session, make_user, make_role):
    make_role("card_ops")
    user = make_user("bob")
    future = datetime.utcnow() + timedelta(days=1)
    _grant(db_session, user, "card_ops", source="project", end_at=future)

    assert get_effective_roles(db_session, user.id) == {"card_ops"}


def test_expired_temporary_role_excluded(db_session, make_user, make_role):
    make_role("card_ops")
    user = make_user("bob")
    past = datetime.utcnow() - timedelta(minutes=1)
    _grant(db_session, user, "card_ops", source="project", end_at=past)

    assert get_effective_roles(db_session, user.id) == set()


def test_revoked_role_excluded_even_if_not_yet_expired(db_session, make_user, make_role):
    make_role("card_ops")
    user = make_user("bob")
    future = datetime.utcnow() + timedelta(days=1)
    _grant(db_session, user, "card_ops", source="project", end_at=future, status="revoked")

    assert get_effective_roles(db_session, user.id) == set()


def test_permanent_and_temporary_roles_combine(db_session, make_user, make_role):
    make_role("compliance_officer")
    make_role("card_ops")
    user = make_user("alice")
    future = datetime.utcnow() + timedelta(days=1)
    _grant(db_session, user, "compliance_officer", source="permanent", end_at=None)
    _grant(db_session, user, "card_ops", source="project", end_at=future)

    assert get_effective_roles(db_session, user.id) == {"compliance_officer", "card_ops"}


def test_as_of_lets_caller_check_a_future_point_in_time(db_session, make_user, make_role):
    """Mirrors demo scenario 3: bob is removed from a project and should lose
    the temporary role once project_end_at passes, without any extra job."""
    make_role("card_ops")
    user = make_user("bob")
    project_end = datetime.utcnow() + timedelta(hours=1)
    _grant(db_session, user, "card_ops", source="project", end_at=project_end)

    assert get_effective_roles(db_session, user.id, as_of=datetime.utcnow()) == {"card_ops"}
    assert get_effective_roles(
        db_session, user.id, as_of=project_end + timedelta(minutes=1)
    ) == set()
