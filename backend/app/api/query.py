import json
import time
from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.core.redis_client import redis_client
from app.models.chat import ChatSession
from app.models.user import User
from app.schemas.query import CitationResponse, ImageQueryResponse, QueryResponse, TextQueryRequest
from app.services.audit import append_audit_log
from app.services.doc_names import cite
from app.services.chat_history import add_message, get_owned_session, load_history, make_title
from app.services.ocr.factory import get_ocr_engine
from app.services.query_service import QueryResult, answer_text_query, plan_text_query, stream_text
from app.services.rbac import get_effective_roles_cached
from app.services.vectorstore.base import PermissionContext

router = APIRouter()

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # mirrors Tencent OCR's own 10MB cap


def _audit_query(
    db: Session,
    *,
    user_id,
    effective_roles: set[str],
    clearance: int,
    compartments: set[str],
    input_type: str,
    recognized_text: str | None,
    question: str,
    retrieved_doc_ids: list[str],
    decision: str,
    deny_reason: str | None,
    latency_ms: int,
    blocked_doc_id: str | None = None,
) -> None:
    append_audit_log(
        db,
        event_type="query",
        user_id=user_id,
        effective_roles=sorted(effective_roles),
        input_type=input_type,
        recognized_text=recognized_text,
        query_text=question,
        normalized_text=question,
        filter_applied={
            "roles": sorted(effective_roles),
            "clearance": clearance,
            "compartments": sorted(compartments),
        },
        retrieved_doc_ids=retrieved_doc_ids,
        blocked_doc_ids=[blocked_doc_id] if blocked_doc_id else [],
        decision=decision,
        deny_reason=deny_reason,
        model_id=settings.llm_backend,
        latency_ms=latency_ms,
    )
    db.commit()


def _run_text_query(
    db: Session,
    current_user: User,
    *,
    question: str,
    input_type: str,
    recognized_text: str | None = None,
) -> QueryResult:
    """Shared by /text and /image: both end up asking the same question
    against the same RBAC-filtered pipeline, just with a different
    input_type/recognized_text for the audit trail."""
    start = time.monotonic()

    effective_roles = get_effective_roles_cached(db, redis_client, current_user.id)
    permission = PermissionContext(
        roles=effective_roles,
        clearance=current_user.clearance,
        compartments=set(current_user.compartments),
    )

    result = answer_text_query(question, permission)

    _audit_query(
        db,
        user_id=current_user.id,
        effective_roles=effective_roles,
        clearance=current_user.clearance,
        compartments=set(current_user.compartments),
        input_type=input_type,
        recognized_text=recognized_text,
        question=question,
        retrieved_doc_ids=result.retrieved_doc_ids,
        decision=result.decision,
        deny_reason=result.deny_reason,
        latency_ms=int((time.monotonic() - start) * 1000),
        blocked_doc_id=result.blocked_doc_id,
    )

    return result


@router.post("/text", response_model=QueryResponse)
def query_text(
    body: TextQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = _run_text_query(db, current_user, question=body.question, input_type="text")

    return QueryResponse(
        decision=result.decision,
        answer=result.answer,
        citations=[CitationResponse(**c) for c in cite(db, result.citations)],
        deny_reason=result.deny_reason,
    )


@contextmanager
def _audit_session():
    """A session of its own for the streaming endpoint: the request-scoped one
    is already closed by the time the response body finishes streaming.
    (Tests replace this to write into their rolled-back transaction.)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/text/stream")
def query_text_stream(
    body: TextQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Same pipeline as /text, delivered as Server-Sent Events:
      meta  - decision + citations + deny_reason, sent as soon as retrieval and
              the RBAC decision are done (before any generation)
      delta - answer text pieces, in order
      done  - end of stream
    Authorization and retrieval happen before the first byte; only the LLM's
    phrasing is streamed. The audit row is written when the stream ends,
    including when the client disconnects early."""
    start = time.monotonic()
    user_id = current_user.id
    clearance = current_user.clearance
    compartments = set(current_user.compartments)
    effective_roles = get_effective_roles_cached(db, redis_client, user_id)
    question = body.question

    # Conversation: continue the caller's own session or open a new one. The
    # earlier turns are loaded before this question is stored.
    if body.session_id is not None:
        session = get_owned_session(db, body.session_id, user_id)
        if session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
        history = load_history(db, session.id)
    else:
        session = ChatSession(user_id=user_id, title=make_title(question))
        db.add(session)
        db.flush()
        history = []
    session_id = session.id
    add_message(db, session_id, "user", question)
    db.commit()

    plan = plan_text_query(
        question,
        PermissionContext(roles=effective_roles, clearance=clearance, compartments=compartments),
        history,
    )
    meta_citations = cite(db, plan.citations)
    answer_parts: list[str] = []

    def events():
        try:
            yield _sse(
                "meta",
                {
                    "session_id": str(session_id),
                    "decision": plan.decision,
                    "deny_reason": plan.deny_reason,
                    "citations": meta_citations,
                },
            )
            if plan.needs_generation:
                for piece in stream_text(question, plan, history):
                    answer_parts.append(piece)
                    yield _sse("delta", {"text": piece})
            elif plan.answer:
                answer_parts.append(plan.answer)
                yield _sse("delta", {"text": plan.answer})
            yield _sse("done", {})
        finally:
            with _audit_session() as audit_db:
                add_message(
                    audit_db,
                    session_id,
                    "assistant",
                    "".join(answer_parts),
                    decision=plan.decision,
                    deny_reason=plan.deny_reason,
                    citations=[{"doc_id": c.doc_id, "snippet": c.snippet} for c in plan.citations],
                )
                _audit_query(
                    audit_db,
                    user_id=user_id,
                    effective_roles=effective_roles,
                    clearance=clearance,
                    compartments=compartments,
                    input_type="text",
                    recognized_text=None,
                    question=question,
                    retrieved_doc_ids=plan.retrieved_doc_ids,
                    decision=plan.decision,
                    deny_reason=plan.deny_reason,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    blocked_doc_id=plan.blocked_doc_id,
                )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/image", response_model=ImageQueryResponse)
async def query_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "图片过大（上限10MB）")

    recognized_text = get_ocr_engine().extract_text(image_bytes)

    if not recognized_text.strip():
        # Nothing to ask the RBAC/retrieval pipeline — not a security event,
        # just a bad upload. Still logged, with decision left unset, so the
        # audit trail distinguishes this from an actual allow/deny.
        append_audit_log(
            db,
            event_type="query",
            user_id=current_user.id,
            input_type="image",
            recognized_text="",
            decision=None,
            deny_reason="OCR 未能从图片中识别出文字",
            model_id=settings.ocr_backend,
        )
        db.commit()
        return ImageQueryResponse(
            decision="allow",
            answer="未能从图片中识别出文字，请换一张更清晰的图片。",
            citations=[],
            deny_reason=None,
            recognized_text="",
        )

    result = _run_text_query(
        db,
        current_user,
        question=recognized_text,
        input_type="image",
        recognized_text=recognized_text,
    )

    return ImageQueryResponse(
        decision=result.decision,
        answer=result.answer,
        citations=[CitationResponse(**c) for c in cite(db, result.citations)],
        deny_reason=result.deny_reason,
        recognized_text=recognized_text,
    )
