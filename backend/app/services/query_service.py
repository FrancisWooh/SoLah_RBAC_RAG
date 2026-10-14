import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass

from app.core.config import settings
from app.services.embeddings.factory import get_embedder
from app.services.llm.factory import get_llm
from app.services.llm.mock_llm import MockLLM
from app.services.vectorstore.base import BlindHit, PermissionContext, ScoredChunk
from app.services.vectorstore.rbac_filter import is_permitted
from app.services.vectorstore.factory import get_vector_store


logger = logging.getLogger(__name__)

_CHUNK_ID = re.compile(r"^(.*)::chunk(\d+)$")


def select_context(good_hits, vector_store, permission):
    """Retrieve many, give few: keep the best serve_k relevant chunks, add the
    neighbouring chunks (same document, so same permissions - re-checked by the
    store) of the top neighbor_top hits, and order the result so each
    document reads in its original order, best-scoring document first."""
    served = list(good_hits[: settings.serve_k])
    get_chunks = getattr(vector_store, "get_chunks", None)
    if get_chunks and settings.neighbor_top > 0 and settings.neighbor_window > 0:
        have = {h.chunk_id for h in served}
        wanted: list[str] = []
        for h in served[: settings.neighbor_top]:
            m = _CHUNK_ID.match(h.chunk_id)
            if not m:
                continue
            for d in range(-settings.neighbor_window, settings.neighbor_window + 1):
                cid = f"{m.group(1)}::chunk{int(m.group(2)) + d}"
                if d and int(m.group(2)) + d >= 0 and cid not in have and cid not in wanted:
                    wanted.append(cid)
        served += get_chunks(wanted, permission)
    doc_rank: dict[str, int] = {}
    for h in served:
        doc_rank.setdefault(h.doc_id, len(doc_rank))

    def chunk_no(h) -> int:
        m = _CHUNK_ID.match(h.chunk_id)
        return int(m.group(2)) if m else 0

    return sorted(served, key=lambda h: (doc_rank[h.doc_id], chunk_no(h)))
LLM_UNAVAILABLE_NOTE = "（大模型暂时不可用，以下为检索到的原文摘录）\n"

# Heuristic only — affects answer/audit wording ("denied" vs "nothing
# found"), never what content is allowed to be returned (vector_store.search()
# already did the exact, non-negotiable RBAC filtering before this file sees
# anything). Empirically chosen for MockEmbedder's score distribution over
# the 4 seed demo docs (genuine matches: 0.24-0.34; same-domain-but-wrong-doc
# noise: 0.15-0.18; unrelated: 0.03-0.08 — see task.txt M4 notes). This MUST
# be re-measured when switching to a real embedder (hunyuan), whose score
# distribution will look nothing like this.
RELEVANCE_THRESHOLD = settings.relevance_threshold

# With a real embedder and a large library, a user's permitted documents
# often clear RELEVANCE_THRESHOLD on topic-adjacent noise (e.g. the employee
# handbook for a leave-policy question) while the genuinely relevant document
# is one they may not see. If the permission-blind best match beats the best
# permitted match by at least this margin, treat the question as one whose
# real answer is restricted and deny instead of answering from the noise.
DENY_MARGIN = settings.deny_margin
# ...unless the user's own best match is already strong: then it is a real
# answer (e.g. the SAR deadline is in the KYC policy they can read, even though
# a restricted STR guideline scores higher), and denying would be a false deny.
# Calibrated on 14 personas x 26 questions: 0 false denies at 0.58.
DENY_STRONG_SCORE = settings.deny_strong_score


@dataclass
class Citation:
    doc_id: str
    snippet: str


@dataclass
class QueryResult:
    decision: str  # "allow" | "deny"
    answer: str | None
    citations: list[Citation]
    deny_reason: str | None
    retrieved_doc_ids: list[str]
    blocked_doc_id: str | None = None  # audit only, never in an API response


def _blind_peek_relevant(
    vector_store, query_vector, top_k: int = 10
) -> tuple[float, list[BlindHit]]:
    """Permission-blind peek: returns (top_score, all_hits).
    The hits carry permission fields so the caller can check is_permitted()
    on each — but never text/doc_id in any user-visible output."""
    peek_relevant = getattr(vector_store, "peek_relevant_hits", None)
    if peek_relevant:
        hits = peek_relevant(query_vector, top_k)
        top_score = hits[0].score if hits else 0.0
        return top_score, hits
    # Fallback for stores that only implement the old interface
    peek_hit = getattr(vector_store, "peek_top_hit", None)
    if peek_hit:
        score, doc_id = peek_hit(query_vector)
        if doc_id:
            return score, [BlindHit(doc_id, score, [], 0, [], "active")]
        return score, []
    return vector_store.peek_top_score(query_vector), []


@dataclass
class QueryPlan:
    """Outcome of retrieval + the allow/deny decision, before any generation.
    Shared by the blocking and the streaming endpoints so both go through the
    exact same RBAC pipeline."""

    decision: str  # "allow" | "deny"
    deny_reason: str | None
    answer: str | None  # fixed answer when no LLM call is needed (deny / nothing found)
    context: list[ScoredChunk]  # chunks the LLM will see; empty when answer is fixed
    citations: list[Citation]
    retrieved_doc_ids: list[str]
    blocked_doc_id: str | None = None  # audit only: best restricted match on a deny

    @property
    def needs_generation(self) -> bool:
        return bool(self.context)


def retrieval_query(question: str, history: list[dict] | None) -> str:
    """Follow-ups ("它的审批流程呢？") are not searchable on their own: prefix the
    user's previous question so retrieval sees the topic. Only the user's own
    earlier words are used; the RBAC filter still runs on the combined query."""
    previous = [m["content"] for m in (history or []) if m["role"] == "user"]
    return f"{previous[-1]}\n{question}" if previous else question


def plan_text_query(
    question: str, permission: PermissionContext, history: list[dict] | None = None
) -> QueryPlan:
    embedder = get_embedder()
    vector_store = get_vector_store()

    search_text = retrieval_query(question, history)
    embed_query = getattr(embedder, "embed_query", None)
    query_vector = embed_query(search_text) if embed_query else embedder.embed_texts([search_text])[0]
    hits = vector_store.search(query_vector, permission, top_k=settings.retrieve_k)

    # ANN search always returns the k nearest permitted vectors, however
    # weak the match — e.g. a query about a document the user can't see
    # will still surface whatever permitted-but-unrelated documents happen
    # to be the "least dissimilar". Only treat a permitted hit as an actual
    # answer once it clears the relevance bar; otherwise fall through to the
    # same "nothing good here" handling as an empty hit list.
    good_hits = [h for h in hits if h.score >= RELEVANCE_THRESHOLD]
    blind_top, blind_hits = _blind_peek_relevant(vector_store, query_vector, settings.retrieve_k)
    best_permitted = max((h.score for h in good_hits), default=0.0)
    restricted_is_better = (
        bool(good_hits) and blind_top - best_permitted >= DENY_MARGIN and best_permitted < DENY_STRONG_SCORE
    )

    if good_hits and not restricted_is_better:
        # The relevance gate (good_hits, used for allow/deny above) stays strict;
        # once passed, slightly weaker chunks may still carry the answer (e.g.
        # cross-lingual hits score ~0.42-0.44), so widen the context pool.
        pool = [h for h in hits if h.score >= settings.serve_floor]
        context = select_context(pool, vector_store, permission)
        return QueryPlan(
            decision="allow",
            deny_reason=None,
            answer=None,
            context=context,
            citations=[Citation(doc_id=h.doc_id, snippet=h.text) for h in context],
            retrieved_doc_ids=list(dict.fromkeys(h.doc_id for h in context)),
        )

    # No good permitted hits. Check if the blind search found ANY relevant
    # docs that were filtered out by RBAC — if so, it's "deny" (no permission).
    # This replaces the old blind_top >= RELEVANCE_THRESHOLD check: looking at
    # ALL blind hits (not just top-1) is robust against query-text dilution
    # shifting the top score below the threshold.
    relevant_blind = [h for h in blind_hits if h.score >= RELEVANCE_THRESHOLD]
    restricted_relevant = [
        h for h in relevant_blind
        if not is_permitted(h.allowed_roles, h.required_clearance, h.compartments, permission)
    ]

    if restricted_relevant:
        best_restricted = max(restricted_relevant, key=lambda h: h.score)
        return QueryPlan(
            decision="deny",
            deny_reason="您当前的角色/密级/分区权限不足以访问与该问题相关的内容",
            answer=None,
            context=[],
            citations=[],
            retrieved_doc_ids=[],
            blocked_doc_id=best_restricted.doc_id,
        )

    return QueryPlan(
        decision="allow",
        deny_reason=None,
        answer="未在知识库中检索到相关内容。",
        context=[],
        citations=[],
        retrieved_doc_ids=[],
    )


def _with_history(llm, question: str, history: list[dict] | None) -> tuple[str, dict]:
    """Backends that take chat history get it as messages; the others (mock,
    deepseek, hunyuan) get the earlier turns folded into the question text."""
    if not history:
        return question, {}
    if getattr(llm, "supports_history", False):
        return question, {"history": history}
    transcript = "\n".join(f"{'用户' if m['role'] == 'user' else '助手'}：{m['content']}" for m in history)
    return f"（此前对话）\n{transcript}\n\n当前问题：{question}", {}


def generate_text(question: str, plan: QueryPlan, history: list[dict] | None = None) -> str:
    """Blocking generation. The LLM only phrases the answer; authorization and
    retrieval already happened, so a failure degrades to the extractive answer
    instead of failing the whole query."""
    try:
        llm = get_llm()
        q, extra = _with_history(llm, question, history)
        return llm.generate_answer(q, plan.context, **extra)
    except Exception:
        logger.exception("LLM generation failed; falling back to extractive answer")
        return LLM_UNAVAILABLE_NOTE + MockLLM().generate_answer(question, plan.context)


def stream_text(question: str, plan: QueryPlan, history: list[dict] | None = None) -> Iterator[str]:
    """Streaming generation: yields text deltas. LLM backends without a native
    stream_answer() yield their whole answer as one delta."""
    llm = get_llm()
    stream = getattr(llm, "stream_answer", None)
    emitted = False
    try:
        q, extra = _with_history(llm, question, history)
        if stream is None:
            yield llm.generate_answer(q, plan.context, **extra)
            return
        for delta in stream(q, plan.context, **extra):
            if delta:
                emitted = True
                yield delta
    except Exception:
        logger.exception("LLM streaming failed")
        if emitted:
            yield "\n\n（回答生成中断）"
        else:
            yield LLM_UNAVAILABLE_NOTE + MockLLM().generate_answer(question, plan.context)


def answer_text_query(
    question: str, permission: PermissionContext, history: list[dict] | None = None
) -> QueryResult:
    plan = plan_text_query(question, permission, history)
    answer = generate_text(question, plan, history) if plan.needs_generation else plan.answer
    return QueryResult(
        decision=plan.decision,
        answer=answer,
        citations=plan.citations,
        deny_reason=plan.deny_reason,
        retrieved_doc_ids=plan.retrieved_doc_ids,
        blocked_doc_id=plan.blocked_doc_id,
    )
