"""Verify the audit-Q&A MCP service the way WorkBuddy will use it: same URL, same
Authorization header, official MCP client. Each scenario replays the tool-call chain an
agent is expected to make for a natural-language question and asserts the facts.

Usage (needs the seeded audit history; see requirement/workbuddy/README.md):
    docker compose exec -T backend python verify_workbuddy_mcp.py [--url http://localhost:8000/mcp/] [--token T]
Without --token it mints a short-lived auditor token itself.
"""

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _mint() -> str:
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.core.security import create_access_token
    from app.models.user import User

    with SessionLocal() as db:
        return create_access_token({"sub": str(db.scalar(select(User.id).where(User.username == "auditor")))}, expires_minutes=30)


async def run(url: str, token: str) -> int:
    failures = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"   {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
        if not ok:
            failures.append(name)

    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            async def call(tool: str, **args):
                res = await s.call_tool(tool, args)
                if res.isError:
                    raise RuntimeError(f"{tool}: {res.content[0].text}")
                out = [json.loads(c.text) if c.text.lstrip().startswith(("{", "[")) else c.text for c in res.content]
                # list-returning tools come back as one content block per element
                return out[0] if len(out) == 1 and isinstance(out[0], (dict, list)) and not _is_row_list(tool) else out

            def _is_row_list(tool):
                return tool in {"audit_summary", "search_audit_logs", "find_documents", "list_audit_logs", "list_users", "list_role_requests"}

            tools = {t.name for t in (await s.list_tools()).tools}
            print(f"connected: {len(tools)} tools -> {sorted(tools)}")
            check("expected tools are exposed", {"get_current_time", "find_documents", "search_audit_logs", "audit_summary", "verify_audit_chain"} <= tools)
            check("no write tools are exposed", not any(t.startswith(("grant", "revoke", "approve", "reject", "delete")) for t in tools))

            print("\nQ1  过去一周谁越权查询过薪酬相关文档？")
            now = await call("get_current_time")
            docs = await call("find_documents", keyword="Compensation")
            comp = [d["doc_id"] for d in docs if "Compensation" in d["title"]]
            check("get_current_time returns SGT", "now_sgt" in now)
            check("find_documents resolves 'Compensation Bands'", "doc_h02" in comp, str(comp))
            blocked = await call("audit_summary", group_by="blocked_document", decision="deny", since_days=7, top=10)
            hit = next((b for b in blocked if b["key"] == "doc_h02"), None)
            check("blocked_document summary lists the compensation bands doc", hit is not None)
            check("...with the users who tried and a count", hit is not None and "bob" in hit["users"] and hit["count"] >= 3, str(hit and (hit["count"], hit["users"])))
            rows = await call("search_audit_logs", doc_id="doc_h02", decision="deny", since_days=7)
            check("rows are attributable (username, time, text, blocked doc title)", bool(rows) and all(r["username"] and r["query_text"] and r["blocked_documents"] for r in rows))

            print("\nQ2  被拒绝次数最多的用户是谁？他们想看什么？")
            by_user = await call("audit_summary", group_by="user", decision="deny", since_days=7)
            check("bob is the top denied user", by_user and by_user[0]["key"] == "bob", str([(b["key"], b["count"]) for b in by_user[:3]]))
            bobs = await call("search_audit_logs", username="bob", decision="deny", since_days=7, limit=50)
            titles = {d.get("title") for r in bobs for d in r["blocked_documents"]}
            check("bob's denials target several restricted documents", len(titles) >= 2, str(sorted(t for t in titles if t)))

            print("\nQ3  昨天有哪些越权尝试？")
            y = await call("search_audit_logs", decision="deny", since_days=2, until_days=1)
            check("window filter (since/until) returns only denials in range", all(r["decision"] == "deny" for r in y), f"{len(y)} rows")

            print("\nQ4  审计日志有没有被篡改？")
            v = await call("verify_audit_chain")
            check("verify_audit_chain ok", v["ok"] is True, f"{v['rows_checked']} rows")

            print("\nQ5  每天的拒绝情况？")
            days = await call("audit_summary", group_by="day", decision="deny", since_days=7)
            check("per-day deny counts", len(days) >= 3, str([(d["key"], d["count"]) for d in days]))

            print("\nSafety")
            allowed = await call("search_audit_logs", decision="allow", since_days=7, limit=5)
            check("allowed rows never carry blocked documents", all(not r["blocked_documents"] for r in allowed))
    print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED: {failures}"))
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/mcp/")
    ap.add_argument("--token")
    a = ap.parse_args()
    raise SystemExit(asyncio.run(run(a.url, a.token or _mint())))
