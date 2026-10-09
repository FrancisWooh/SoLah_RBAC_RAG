import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.services.doc_names import cite
from app.services.chat_history import get_owned_session

router = APIRouter()


class SessionSummary(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    decision: str | None
    deny_reason: str | None
    citations: list | None
    created_at: datetime


class SessionDetail(SessionSummary):
    messages: list[MessageOut]


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(ChatSession).where(ChatSession.user_id == current_user.id).order_by(ChatSession.updated_at.desc()).limit(200)
    ).scalars()
    return [SessionSummary(id=s.id, title=s.title, updated_at=s.updated_at) for s in rows]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_owned_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    messages = db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.id)
    ).scalars().all()
    return SessionDetail(
        id=session.id,
        title=session.title,
        updated_at=session.updated_at,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                decision=m.decision,
                deny_reason=m.deny_reason,
                citations=cite(db, m.citations) if m.citations else m.citations,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_owned_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    db.query(ChatMessage).filter(ChatMessage.session_id == session.id).delete()
    db.delete(session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
