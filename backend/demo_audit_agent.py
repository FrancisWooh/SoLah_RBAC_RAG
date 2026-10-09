"""Stand-in for WorkBuddy: a small Claude tool-use loop over the SAME MCP connection and the SAME
agent instructions (requirement/workbuddy/audit_agent_prompt.md). Use it to sanity-check the tool
surface and the prompt when WorkBuddy itself is not at hand. It is NOT WorkBuddy - a different model
will phrase and plan differently - and each question makes a few paid Claude API calls.

Usage: python demo_audit_agent.py "过去一周谁越权查询过薪酬相关文档？" ["second question" ...]
"""

import asyncio
import re
import sys
from pathlib import Path

import anthropic
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings
from verify_workbuddy_mcp import _mint

PROMPT_FILE = Path(__file__).parent.parent / "requirement" / "workbuddy" / "audit_agent_prompt.md"
URL = "http://localhost:8000/mcp/"


async def ask(question: str) -> None:
    system = PROMPT_FILE.read_text(encoding="utf-8") if PROMPT_FILE.exists() else "You are an internal audit assistant."
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    async with streamablehttp_client(URL, headers={"Authorization": f"Bearer {_mint()}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in (await s.list_tools()).tools]
            messages = [{"role": "user", "content": question}]
            print(f"\n=== {question}")
            for _ in range(10):
                resp = client.messages.create(
                    model=settings.anthropic_model, max_tokens=4000, system=system, tools=tools, messages=messages,
                    output_config={"effort": "low"},
                )
                messages.append({"role": "assistant", "content": resp.content})
                calls = [b for b in resp.content if b.type == "tool_use"]
                if not calls:
                    print("\n" + "".join(b.text for b in resp.content if b.type == "text"))
                    return
                results = []
                for c in calls:
                    shown = ", ".join(f"{k}={v!r}" for k, v in c.input.items())
                    print(f"  -> {c.name}({shown})")
                    res = await s.call_tool(c.name, c.input)
                    text = "\n".join(x.text for x in res.content)
                    results.append({"type": "tool_result", "tool_use_id": c.id, "content": text[:12000], "is_error": bool(res.isError)})
                messages.append({"role": "user", "content": results})
            print("(stopped: too many tool rounds)")


if __name__ == "__main__":
    for q in sys.argv[1:]:
        asyncio.run(ask(q))
