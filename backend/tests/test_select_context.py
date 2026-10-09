"""'Retrieve many, give few': context selection for the LLM."""

from app.services import query_service
from app.services.vectorstore.base import PermissionContext, ScoredChunk

PERM = PermissionContext({"employee"}, 1, set())


def _c(doc, n, score=0.0):
    return ScoredChunk(f"{doc}::chunk{n}", doc, f"{doc} text {n}", score, ["employee"], 1, [])


class _Store:
    """Has every chunk 0..9 of every doc; records what get_chunks was asked for."""

    def __init__(self):
        self.asked = []

    def get_chunks(self, chunk_ids, permission):
        self.asked.append(list(chunk_ids))
        out = []
        for cid in chunk_ids:
            doc, n = cid.split("::chunk")
            if 0 <= int(n) <= 9:
                out.append(_c(doc, int(n)))
        return out


def _cfg(monkeypatch, serve_k=5, neighbor_top=2, neighbor_window=1):
    monkeypatch.setattr(query_service.settings, "serve_k", serve_k)
    monkeypatch.setattr(query_service.settings, "neighbor_top", neighbor_top)
    monkeypatch.setattr(query_service.settings, "neighbor_window", neighbor_window)


def test_serves_best_k_plus_neighbours_in_reading_order(monkeypatch):
    _cfg(monkeypatch, serve_k=3)
    hits = [_c("doc_a", 4, 0.9), _c("doc_b", 2, 0.8), _c("doc_a", 1, 0.7), _c("doc_c", 0, 0.6)]
    store = _Store()

    ctx = query_service.select_context(hits, store, PERM)

    ids = [h.chunk_id for h in ctx]
    # only 3 of the 4 relevant hits are served (doc_c dropped); neighbours of the top 2 added
    assert "doc_c::chunk0" not in ids
    assert ids == [
        "doc_a::chunk1", "doc_a::chunk3", "doc_a::chunk4", "doc_a::chunk5",  # best doc first, in order
        "doc_b::chunk1", "doc_b::chunk2", "doc_b::chunk3",
    ]


def test_neighbours_never_duplicate_and_stop_at_document_start(monkeypatch):
    _cfg(monkeypatch)
    store = _Store()
    ctx = query_service.select_context([_c("doc_a", 0, 0.9), _c("doc_a", 1, 0.8)], store, PERM)
    assert [h.chunk_id for h in ctx] == ["doc_a::chunk0", "doc_a::chunk1", "doc_a::chunk2"]
    assert store.asked == [["doc_a::chunk2"]]  # chunk -1 never requested; chunk0/1 already held


def test_neighbour_expansion_can_be_disabled(monkeypatch):
    _cfg(monkeypatch, neighbor_top=0)
    store = _Store()
    ctx = query_service.select_context([_c("doc_a", 4, 0.9)], store, PERM)
    assert [h.chunk_id for h in ctx] == ["doc_a::chunk4"] and store.asked == []


def test_store_without_get_chunks_still_works(monkeypatch):
    _cfg(monkeypatch)
    ctx = query_service.select_context([_c("doc_a", 4, 0.9)], object(), PERM)
    assert [h.chunk_id for h in ctx] == ["doc_a::chunk4"]
