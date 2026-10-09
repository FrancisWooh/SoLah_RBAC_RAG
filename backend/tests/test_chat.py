"""Conversation history: sessions are stored, owner-only, and earlier turns
are replayed to the LLM on follow-up questions."""

import contextlib
import json

import pytest

from app.api import query as query_api
from app.core.db import get_db
from app.main import app
from app.services import query_service


class _RecordingLLM:
    supports_history = True

    def __init__(self):
        self.calls = []

    def stream_answer(self, question, chunks, history=None):
        self.calls.append((question, history))
        yield "回答:" + question


@pytest.fixture()
def client(db_session, test_client, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db_session

    @contextlib.contextmanager
    def audit_session():
        yield db_session

    monkeypatch.setattr(query_api, "_audit_session", audit_session)
    yield test_client
    app.dependency_overrides.clear()


def _auth(client, username):
    token = client.post("/api/auth/login", json={"username": username}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _ask(client, headers, question, session_id=None):
    body = {"question": question, **({"session_id": session_id} if session_id else {})}
    resp = client.post("/api/query/text/stream", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    first = resp.text.strip().split("\n\n")[0]
    return json.loads(first.split("\n", 1)[1].removeprefix("data: "))


def test_follow_up_carries_history_and_is_persisted(client, monkeypatch):
    llm = _RecordingLLM()
    monkeypatch.setattr(query_service, "get_llm", lambda: llm)
    h = _auth(client, "alice")

    meta1 = _ask(client, h, "KYC/AML 审核标准是什么？")
    sid = meta1["session_id"]
    assert llm.calls[-1][1] is None

    _ask(client, h, "那审核频率呢？", sid)
    q2, hist = llm.calls[-1]
    assert q2 == "那审核频率呢？"
    assert [m["role"] for m in hist] == ["user", "assistant"]
    assert hist[0]["content"] == "KYC/AML 审核标准是什么？"

    detail = client.get(f"/api/chat/sessions/{sid}", headers=h).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["title"].startswith("KYC/AML")
    assert sid in [s["id"] for s in client.get("/api/chat/sessions", headers=h).json()]


def test_sessions_are_owner_only(client, monkeypatch):
    monkeypatch.setattr(query_service, "get_llm", lambda: _RecordingLLM())
    sid = _ask(client, _auth(client, "alice"), "KYC/AML 审核标准是什么？")["session_id"]
    other = _auth(client, "bob")

    assert client.get(f"/api/chat/sessions/{sid}", headers=other).status_code == 404
    assert client.delete(f"/api/chat/sessions/{sid}", headers=other).status_code == 404
    assert client.post("/api/query/text/stream", json={"question": "x", "session_id": sid}, headers=other).status_code == 404


def test_delete_session(client, monkeypatch):
    monkeypatch.setattr(query_service, "get_llm", lambda: _RecordingLLM())
    h = _auth(client, "alice")
    sid = _ask(client, h, "KYC/AML 审核标准是什么？")["session_id"]
    assert client.delete(f"/api/chat/sessions/{sid}", headers=h).status_code == 204
    assert client.get(f"/api/chat/sessions/{sid}", headers=h).status_code == 404
