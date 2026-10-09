"""Back-fill a week of plausible query activity into the audit trail so the
audit Q&A (WorkBuddy over MCP) and the Dashboard have something to analyse.

Every row goes through the REAL retrieval/RBAC pipeline (no LLM is called), so
decisions, served documents and blocked documents are what the system would
actually have produced; only the timestamps are back-dated. Rows are marked
model_id="seed-history" so they can always be told apart from live traffic.
Run once, after seed_data.py and seed_vectorstore.py (start.sh does).

Usage: python seed_audit_history.py
"""

import time
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.redis_client import redis_client
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit import append_audit_log
from app.services.query_service import plan_text_query
from app.services.rbac import get_effective_roles_cached
from app.services.vectorstore.base import PermissionContext

MARKER = "seed-history"

# (days ago, UTC hour, user, question) - oldest first so the hash chain follows time
HISTORY = [
    (6, 1, "alice", "KYC/AML 审核标准是什么？"),
    (6, 2, "henry", "年假政策有多少天？"),
    (6, 3, "frank", "How long do I have to do the first classification of a customer complaint?"),
    (6, 6, "gina", "What was the Q3 net loss?"),
    (5, 1, "carol", "How often is the sanctions list refreshed and who handles a true match?"),
    (5, 2, "bob", "Compensation band for grade G5"),
    (5, 3, "kate", "What is the SEV1 incident acknowledgement time?"),
    (5, 6, "ivy", "What does the brand guideline say about logo clear space?"),
    (4, 1, "bob", "What are the salary ranges by grade at Aspire?"),
    (4, 2, "frank", "What was Q3 revenue and net loss?"),
    (4, 3, "dave", "How often is the sanctions list refreshed and who handles a true match?"),
    (4, 5, "erin", "What is the chargeback filing window in days?"),
    (4, 7, "alice", "年假政策有多少天？"),
    (3, 1, "bob", "Compensation band for grade G5"),
    (3, 2, "jack", "Due diligence findings on PayNest"),
    (3, 3, "leo", "How long to notify PDPC of a data breach?"),
    (3, 4, "bob", "What did the board decide about the FY2027 budget?"),
    (3, 6, "gina", "What was Q3 revenue and net loss?"),
    (3, 8, "alice", "How often is the sanctions list refreshed and who handles a true match?"),
    (2, 1, "bob", "What is the executive compensation structure?"),
    (2, 2, "ivy", "What are the compensation bands by grade?"),
    (2, 3, "vera", "What did the board decide about the FY2027 budget?"),
    (2, 4, "erin", "What credit limit multiplier applies to a band B SME applicant?"),
    (2, 6, "carol", "可疑交易报告 SAR 要在多长时间内提交？"),
    (2, 8, "bob", "Compensation band for grade G5"),
    (1, 1, "alice", "KYC/AML 审核标准是什么？"),
    (1, 2, "frank", "What was the Q3 net loss?"),
    (1, 3, "dave", "What late-payment interest rate applies on overdue card balances?"),
    (1, 4, "jack", "Valuation range for the PayNest acquisition"),
    (1, 5, "kate", "How fast must leaver access be revoked?"),
    (1, 6, "bob", "Due diligence findings on PayNest"),
    (1, 8, "henry", "G5 salary band"),
    (0, 0, "alice", "年假政策有多少天？"),
    (0, 1, "ivy", "Who approves press releases?"),
    (0, 2, "frank", "What is the Q3 revenue and net loss for the company?"),
    (0, 3, "gina", "How much did the board approve for the Vietnam launch?"),
    (0, 4, "carol", "STR filing guideline deadline"),
]


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(AuditLog.id).where(AuditLog.model_id == MARKER).limit(1)) is not None:
            print("audit history already seeded; nothing to do")
            return
        users = {u.username: u for u in db.scalars(select(User))}
        now = datetime.utcnow().replace(minute=17, second=0, microsecond=0)
        denies = 0
        for i, (days, hour, username, question) in enumerate(HISTORY):
            user = users[username]
            roles = get_effective_roles_cached(db, redis_client, user.id)
            perm = PermissionContext(roles=roles, clearance=user.clearance, compartments=set(user.compartments))
            started = time.monotonic()
            plan = plan_text_query(question, perm)
            append_audit_log(
                db,
                event_type="query",
                user_id=user.id,
                effective_roles=sorted(roles),
                input_type="text",
                query_text=question,
                normalized_text=question,
                filter_applied={"roles": sorted(roles), "clearance": user.clearance, "compartments": sorted(user.compartments)},
                retrieved_doc_ids=plan.retrieved_doc_ids,
                blocked_doc_ids=[plan.blocked_doc_id] if plan.blocked_doc_id else [],
                decision=plan.decision,
                deny_reason=plan.deny_reason,
                model_id=MARKER,
                latency_ms=900 + (i * 331) % 3800 + int((time.monotonic() - started) * 1000),
                created_at=(now - timedelta(days=days)).replace(hour=hour, minute=(i * 7) % 60),
            )
            denies += plan.decision == "deny"
            print(f"  {days}d ago {hour:02d}h {username:6} {plan.decision:5} blocked={plan.blocked_doc_id} | {question[:56]}")
        db.commit()
        print(f"seeded {len(HISTORY)} audit rows ({denies} denied)")


if __name__ == "__main__":
    main()
