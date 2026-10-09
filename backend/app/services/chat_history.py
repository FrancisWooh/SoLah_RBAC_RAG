import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession

# How many earlier messages (user + assistant) are replayed to the model.
HISTORY_MESSAGES = 10
TITLE_MAX = 30


def get_owned_session(db: Session, session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession | None:
    """A session is visible to its owner only; anyone else gets None (-> 404)."""
    return db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    ).scalar_one_or_none()


def make_title(question: str) -> str:
    one_line = " ".join(question.split())
    return one_line[:TITLE_MAX] + ("…" if len(one_line) > TITLE_MAX else "")


def load_history(db: Session, session_id: uuid.UUID) -> list[dict]:
    """Earlier turns as [{role, content}], oldest first. A turn whose answer was
    denied (or empty) is dropped entirely, so the model never sees a question
    without an answer and denied topics are not carried into retrieval."""
    rows = (
        db.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.desc()).limit(HISTORY_MESSAGES)
        )
        .scalars()
        .all()
    )[::-1]
    history: list[dict] = []
    pending: ChatMessage | None = None
    for m in rows:
        if m.role == "user":
            pending = m
        elif m.role == "assistant" and pending is not None:
            if m.decision == "allow" and m.content:
                history += [
                    {"role": "user", "content": pending.content},
                    {"role": "assistant", "content": m.content},
                ]
            pending = None
    return history


def add_message(db: Session, session_id: uuid.UUID, role: str, content: str, **extra) -> ChatMessage:
    msg = ChatMessage(session_id=session_id, role=role, content=content, **extra)
    db.add(msg)
    session = db.get(ChatSession, session_id)
    if session is not None:
        session.updated_at = datetime.utcnow()
    return msg
