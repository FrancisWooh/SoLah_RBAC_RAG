from dataclasses import dataclass
from typing import Protocol


@dataclass
class VectorChunk:
    chunk_id: str
    doc_id: str
    text: str
    vector: list[float]
    allowed_roles: list[str]
    required_clearance: int
    compartments: list[str]
    version: str = "v1"
    status: str = "active"


@dataclass
class ScoredChunk:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    allowed_roles: list[str]
    required_clearance: int
    compartments: list[str]
    version: str = "v1"
    status: str = "active"


@dataclass
class PermissionContext:
    roles: set[str]
    clearance: int
    compartments: set[str]


@dataclass
class BlindHit:
    """Permission-blind peek result. No text field by design: the caller
    must never expose content to the asking user. Only score, doc_id (for
    audit), and permission fields (so is_permitted can run on each hit)."""
    doc_id: str
    score: float
    allowed_roles: list[str]
    required_clearance: int
    compartments: list[str]
    status: str = "active"


class VectorStore(Protocol):
    def upsert(self, chunks: list[VectorChunk]) -> None: ...

    def delete_doc(self, doc_id: str) -> None:
        """Remove every chunk of a document (re-index, supersede, file removed)."""
        ...

    def search(
        self, query_vector: list[float], permission: PermissionContext, top_k: int = 5
    ) -> list[ScoredChunk]: ...

    def get_chunks(self, chunk_ids: list[str], permission: PermissionContext) -> list[ScoredChunk]:
        """Fetch specific chunks by id (score 0.0), e.g. the neighbours of a hit.
        Must apply the same exact permission/status gate as search()."""
        ...

    def peek_top_hit(self, query_vector: list[float]) -> tuple[float, str | None]:
        """Like peek_top_score, but also returns the doc_id of that best match,
        permission-blind. ONLY for the audit trail (which restricted document a
        denied user was after): the caller must never put the id in anything the
        asking user can see."""
        ...

    def peek_top_score(self, query_vector: list[float]) -> float:
        """Permission-BLIND similarity peek, used only to tell apart "nothing
        relevant exists" from "something relevant exists but you can't see
        it" for audit/deny-reason wording. Must return a bare float — never
        a doc_id, title or any content, since whoever asked for this may not
        be authorized to know the document exists at all."""
        ...

    def peek_relevant_hits(
        self, query_vector: list[float], top_k: int = 10
    ) -> list["BlindHit"]:
        """Permission-blind search returning all hits (up to top_k) that are
        NOT archived/deleted, with their permission fields so the caller can
        run is_permitted() on each. Like peek_top_hit, the doc_ids are for
        audit/decision logic only — never put them in an API response."""
        ...
