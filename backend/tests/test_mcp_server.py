"""The MCP tool functions are plain Python functions under the @mcp_app.tool()
decorator (verified: the decorator registers and returns the original
callable unchanged), so they're called directly here with a minimal fake
Context — no real MCP transport needed for these tests. The transport
itself (streamable-http, real ctx.request_context.request wiring, tool
discovery) was verified manually with the real `mcp` client library against
the running dev server, see task.txt M10 notes; that's not something a fake
Context can exercise, so it isn't re-proven here.

All tools here are read-only, so they use the real SessionLocal() (same as
in production) rather than the db_session test-transaction fixture — there
is nothing to roll back.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import create_access_token
from app.mcp_server import (
    McpAuthError,
    get_dashboard_stats,
    get_user_roles,
    list_audit_logs,
    list_role_requests,
    list_users,
    verify_audit_chain,
)
from app.models.user import User


class _FakeRequest:
    def __init__(self, headers: dict):
        self.headers = headers


class _FakeRequestContext:
    def __init__(self, request):
        self.request = request


class _FakeCtx:
    def __init__(self, token: str | None = None):
        headers = {"authorization": f"Bearer {token}"} if token else {}
        self.request_context = _FakeRequestContext(_FakeRequest(headers))


def _token_for(username: str) -> str:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        return create_access_token({"sub": str(user.id)})


def _user_id(username: str) -> str:
    with SessionLocal() as db:
        return str(db.scalar(select(User).where(User.username == username)).id)


def test_tool_without_token_is_rejected():
    with pytest.raises(McpAuthError, match="缺少 Authorization"):
        list_users(_FakeCtx())


def test_tool_with_non_admin_token_is_rejected():
    with pytest.raises(McpAuthError, match="权限不足"):
        list_users(_FakeCtx(_token_for("bob")))


def test_tool_with_garbage_token_is_rejected():
    with pytest.raises(McpAuthError, match="无效或已过期"):
        list_users(_FakeCtx("not-a-real-jwt"))


def test_list_users_returns_real_seeded_users():
    users = list_users(_FakeCtx(_token_for("admin")))
    assert {u["username"] for u in users} >= {"alice", "bob", "admin"}


def test_get_user_roles_returns_real_grants():
    alice_id = _user_id("alice")
    roles = get_user_roles(_FakeCtx(_token_for("admin")), alice_id)
    assert any(r["role_id"] == "compliance_officer" for r in roles)


def test_list_audit_logs_filters_by_user_and_decision():
    alice_id = _user_id("alice")
    logs = list_audit_logs(
        _FakeCtx(_token_for("admin")),
        user_id=alice_id,
        decision="deny",
        since_days=7,
    )
    assert all(log["user_id"] == alice_id for log in logs)
    assert all(log["decision"] == "deny" for log in logs)


def test_list_audit_logs_since_days_excludes_older_rows():
    # sanity check on the since_days -> start_time conversion itself
    alice_id = _user_id("alice")
    far_future_window = list_audit_logs(
        _FakeCtx(_token_for("admin")), user_id=alice_id, since_days=36500
    )
    recent_window = list_audit_logs(
        _FakeCtx(_token_for("admin")), user_id=alice_id, since_days=1
    )
    assert len(far_future_window) >= len(recent_window)


def test_list_role_requests_is_queryable_and_filterable_by_status():
    all_requests = list_role_requests(_FakeCtx(_token_for("admin")))
    pending_only = list_role_requests(_FakeCtx(_token_for("admin")), status="pending")
    assert all(r["status"] == "pending" for r in pending_only)
    assert len(pending_only) <= len(all_requests)


def test_verify_audit_chain_reports_ok_for_untampered_chain():
    result = verify_audit_chain(_FakeCtx(_token_for("admin")))
    assert result["ok"] is True


def test_get_dashboard_stats_returns_consistent_totals():
    # total_queries can exceed allow+deny: a query event is logged with
    # decision=None for the "OCR found no text" case (see query.py /image
    # endpoint) since that's a bad upload, not an allow/deny security event.
    stats = get_dashboard_stats(_FakeCtx(_token_for("admin")))
    assert stats["total_queries"] >= stats["allow_count"] + stats["deny_count"]


# --- audit Q&A tools (search / summary / documents / time) --------------------
# Read-only, use the real database. Shape and behaviour checks only, so they hold
# whatever traffic happens to be in the audit trail.

from app.mcp_server import audit_summary, find_documents, get_current_time, search_audit_logs  # noqa: E402


def _auditor_token() -> str:
    return _token_for("auditor")


def test_auditor_identity_can_use_tools_but_a_normal_user_cannot():
    assert get_current_time(_FakeCtx(_auditor_token()))["now_sgt"]
    with pytest.raises(McpAuthError):
        get_current_time(_FakeCtx(_token_for("alice")))


def test_find_documents_resolves_a_title_word_to_doc_ids_and_metadata():
    docs = find_documents(_FakeCtx(_auditor_token()), "Compensation")
    assert any(d["doc_id"] == "doc_h02" and d["department"] == "hr" and d["required_clearance"] == 3 for d in docs)
    assert all({"doc_id", "title", "department"} <= d.keys() for d in docs)


def test_search_rows_carry_usernames_and_document_titles():
    rows = search_audit_logs(_FakeCtx(_auditor_token()), decision="deny", limit=20)
    for r in rows:
        assert r["decision"] == "deny" and r["username"]
        assert all("title" in d or "doc_id" in d for d in r["blocked_documents"])


def test_search_by_unknown_user_is_a_clear_error_and_filters_combine():
    with pytest.raises(ValueError):
        search_audit_logs(_FakeCtx(_auditor_token()), username="nobody-here")
    rows = search_audit_logs(_FakeCtx(_auditor_token()), username="alice", decision="deny", since_days=30)
    assert all(r["username"] == "alice" and r["decision"] == "deny" for r in rows)


def test_audit_summary_groups_validates_and_sorts():
    ctx = _FakeCtx(_auditor_token())
    for group in ("user", "day", "decision", "event_type", "blocked_document", "served_document"):
        rows = audit_summary(ctx, group_by=group, since_days=365)
        assert all({"key", "count"} <= r.keys() for r in rows)
        if group not in ("day",):
            assert [r["count"] for r in rows] == sorted((r["count"] for r in rows), reverse=True)
    blocked = audit_summary(ctx, group_by="blocked_document", since_days=365)
    assert all(isinstance(r["users"], list) for r in blocked)
    with pytest.raises(ValueError):
        audit_summary(ctx, group_by="password")
