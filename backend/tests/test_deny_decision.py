"""allow/deny wording decision in answer_text_query, with scripted scores."""

from types import SimpleNamespace as NS

import pytest

from app.services import query_service
from app.services.vectorstore.base import BlindHit, PermissionContext, ScoredChunk

# The real threshold may be overridden by env (e.g. 0.42 in the dev container);
# use it so the scripted scores are always on the correct side of the bar.
TH = query_service.RELEVANCE_THRESHOLD


class _Embedder:
    dim = 3

    def embed_texts(self, texts):
        return [[0.0, 0.0, 0.0] for _ in texts]


class _Store:
    def __init__(self, permitted_score, blind_score, *,
                 blind_doc_restricted=True, blind_hits=None):
        self._hits = (
            [ScoredChunk("c", "doc_permitted", "text", permitted_score, ["employee"], 1, [])]
            if permitted_score is not None
            else []
        )
        self._blind_score = blind_score
        self._blind_hits = blind_hits  # explicit list overrides score-based logic
        self._blind_doc_restricted = blind_doc_restricted

    def search(self, vector, permission, top_k=5):
        return self._hits

    def peek_relevant_hits(self, vector, top_k=10):
        if self._blind_hits is not None:
            return self._blind_hits
        if self._blind_score < TH:
            return []
        if self._blind_doc_restricted:
            return [BlindHit("doc_restricted", self._blind_score, ["compliance"], 3, [])]
        return [BlindHit("doc_permitted", self._blind_score, ["employee"], 1, [])]

    def peek_top_score(self, vector):  # kept for backward-compat fallback
        return self._blind_score


class _LLM:
    def generate_answer(self, question, chunks):
        return "generated"


def _run(monkeypatch, permitted, blind, **kwargs):
    monkeypatch.setattr(query_service, "get_embedder", lambda: _Embedder())
    monkeypatch.setattr(query_service, "get_vector_store", lambda: _Store(permitted, blind, **kwargs))
    monkeypatch.setattr(query_service, "get_llm", lambda: _LLM())
    return query_service.answer_text_query("q", PermissionContext({"employee"}, 1, set()))


def test_weak_permitted_match_with_much_better_restricted_match_is_denied(monkeypatch):
    # e.g. alice asking about leave: handbook noise 0.51 vs restricted HR policy 0.78
    assert _run(monkeypatch, 0.51, 0.78).decision == "deny"


def test_strong_permitted_match_is_answered_even_if_restricted_scores_higher(monkeypatch):
    # e.g. alice asking the SAR deadline: her KYC policy 0.61 vs restricted STR guideline 0.77
    result = _run(monkeypatch, 0.61, 0.77)
    assert result.decision == "allow" and result.answer == "generated"


def test_no_permitted_hit_but_relevant_restricted_doc_is_denied(monkeypatch):
    assert _run(monkeypatch, None, 0.75).decision == "deny"


def test_nothing_relevant_anywhere_is_allow_with_no_citations(monkeypatch):
    result = _run(monkeypatch, 0.30, 0.31)
    assert result.decision == "allow" and result.citations == []


def test_restricted_doc_not_top_hit_but_still_relevant_is_denied(monkeypatch):
    """The restricted doc isn't the #1 blind hit (noise scores higher) but IS
    above relevance threshold — old code only checked top score and would miss it."""
    result = _run(monkeypatch, None, TH - 0.01,
        blind_hits=[
            BlindHit("doc_noise", TH - 0.01, ["employee"], 1, []),
            BlindHit("doc_restricted", TH + 0.01, ["compliance"], 3, []),
        ])
    assert result.decision == "deny"
