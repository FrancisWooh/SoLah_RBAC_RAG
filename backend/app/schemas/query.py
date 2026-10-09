import uuid

from pydantic import BaseModel


class TextQueryRequest(BaseModel):
    question: str
    session_id: uuid.UUID | None = None  # continue this conversation; omitted = start a new one


class CitationResponse(BaseModel):
    doc_id: str
    snippet: str
    filename: str | None = None


class QueryResponse(BaseModel):
    decision: str  # "allow" | "deny"
    answer: str | None
    citations: list[CitationResponse]
    deny_reason: str | None


class ImageQueryResponse(QueryResponse):
    recognized_text: str
