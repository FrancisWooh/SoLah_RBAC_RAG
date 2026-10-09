"""POST /api/query/text/stream (Server-Sent Events), against the real seeded
library like test_query.py; only the LLM is replaced by a scripted fake."""

import contextlib
import json

import pytest
from sqlalchemy import select

from app.api import query as query_api
from app.core.db import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services import query_service


class _FakeLLM:
    def __init__(self, deltas, fail_after=None):
        self.deltas, self.fail_after = deltas, fail_after

    def stream_answer(self, question, chunks):
        for i, d in enumerate(self.deltas):
            if self.fail_after is not None and i >= self.fail_after:
                raise RuntimeError("stream broke")
            yield d


@pytest.fixture()
def client(db_session, test_client, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db_session

    @contextlib.contextmanager
    def audit_session():
        yield db_session  # keep audit writes inside the rolled-back test transaction

    monkeypatch.setattr(query_api, "_audit_session", audit_session)
    yield test_client
    app.dependency_overrides.clear()


def _stream(client, username, question):
    token = client.post("/api/auth/login", json={"username": username}).json()["access_token"]
    resp = client.post("/api/query/text/stream", json={"question": question}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in resp.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def _audit_rows(db_session, username, question):
    uid = db_session.scalar(select(User.id).where(User.username == username))
    return db_session.scalars(
        select(AuditLog).where(AuditLog.user_id == uid, AuditLog.query_text == question).order_by(AuditLog.id)
    ).all()


def test_allowed_query_streams_meta_then_ordered_deltas_then_done(client, db_session, monkeypatch):
    monkeypatch.setattr(query_service, "get_llm", lambda: _FakeLLM(["KYC ", "answer ", "[doc]"]))
    q = "KYC/AML 审核标准是什么？"

    events = _stream(client, "alice", q)

    names = [n for n, _ in events]
    assert names == ["meta", "delta", "delta", "delta", "done"]
    meta = events[0][1]
    assert meta["decision"] == "allow" and "doc_kyc_aml_policy" in {c["doc_id"] for c in meta["citations"]}
    assert "".join(d["text"] for n, d in events if n == "delta") == "KYC answer [doc]"
    rows = _audit_rows(db_session, "alice", q)
    assert rows and rows[-1].decision == "allow" and rows[-1].input_type == "text"


def test_denied_query_streams_no_text_and_never_calls_the_llm(client, db_session, monkeypatch):
    monkeypatch.setattr(query_service, "get_llm", lambda: pytest.fail("LLM must not be called on deny"))
    q = "年假政策有多少天？"

    events = _stream(client, "alice", q)

    assert [n for n, _ in events] == ["meta", "done"]
    assert events[0][1]["decision"] == "deny" and events[0][1]["deny_reason"] and events[0][1]["citations"] == []
    assert _audit_rows(db_session, "alice", q)[-1].decision == "deny"


def test_stream_that_breaks_midway_is_marked_interrupted(client, monkeypatch):
    monkeypatch.setattr(query_service, "get_llm", lambda: _FakeLLM(["part one ", "never"], fail_after=1))

    events = _stream(client, "alice", "KYC/AML 审核标准是什么？")

    text = "".join(d["text"] for n, d in events if n == "delta")
    assert text.startswith("part one ") and "回答生成中断" in text and events[-1][0] == "done"


def test_stream_requires_auth(client):
    assert client.post("/api/query/text/stream", json={"question": "x"}).status_code in (401, 403)
