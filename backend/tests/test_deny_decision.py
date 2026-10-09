"""allow/deny wording decision in answer_text_query, with scripted scores."""

from types import SimpleNamespace as NS

import pytest

from app.services import query_service
from app.services.vectorstore.base import PermissionContext, ScoredChunk


class _Embedder:
    dim = 3

    def embed_texts(self, texts):
        return [[0.0, 0.0, 0.0] for _ in texts]


class _Store:
    def __init__(self, permitted_score, blind_score):
        self._hits = (
            [ScoredChunk("c", "doc_permitted", "text", permitted_score, ["employee"], 1, [])]
            if permitted_score is not None
            else []
        )
        self._blind = blind_score

    def search(self, vector, permission, top_k=5):
        return self._hits

    def peek_top_score(self, vector):
        return self._blind


class _LLM:
    def generate_answer(self, question, chunks):
        return "generated"


def _run(monkeypatch, permitted, blind):
    monkeypatch.setattr(query_service, "get_embedder", lambda: _Embedder())
    monkeypatch.setattr(query_service, "get_vector_store", lambda: _Store(permitted, blind))
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
