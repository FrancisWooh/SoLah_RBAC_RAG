"""Integration tests against the real Qdrant container (not mocked) — this
is the single most important correctness property in the whole project:
a user must never get back a chunk they are not authorized for.
"""

from app.services.embeddings.mock_embedder import MockEmbedder
from app.services.vectorstore.base import PermissionContext, VectorChunk
from app.services.vectorstore.qdrant_store import QdrantVectorStore
from app.services.vectorstore.rbac_filter import filter_hits_by_permission, is_permitted

TEST_COLLECTION = "test_knowledge_chunks"


def _store():
    return QdrantVectorStore(collection=TEST_COLLECTION, dim=32)


def _embed(text: str) -> list[float]:
    return MockEmbedder(dim=32).embed_texts([text])[0]


def _seed(store: QdrantVectorStore):
    store.upsert(
        [
            VectorChunk(
                chunk_id="doc_kyc::chunk0",
                doc_id="doc_kyc",
                text="KYC/AML 审核标准",
                vector=_embed("KYC/AML 审核标准"),
                allowed_roles=["compliance_officer"],
                required_clearance=2,
                compartments=["aml"],
            ),
            VectorChunk(
                chunk_id="doc_support::chunk0",
                doc_id="doc_support",
                text="客户投诉处理 SOP",
                vector=_embed("客户投诉处理 SOP"),
                allowed_roles=["customer_support"],
                required_clearance=1,
                compartments=[],
            ),
            VectorChunk(
                chunk_id="doc_public::chunk0",
                doc_id="doc_public",
                text="公司通用行为准则",
                vector=_embed("公司通用行为准则"),
                allowed_roles=["employee"],
                required_clearance=1,
                compartments=[],
            ),
        ]
    )


def test_matching_role_and_clearance_returns_the_doc():
    store = _store()
    _seed(store)
    permission = PermissionContext(roles={"compliance_officer", "employee"}, clearance=2, compartments={"aml"})

    hits = store.search(_embed("KYC/AML 审核标准"), permission, top_k=5)

    assert {h.doc_id for h in hits} == {"doc_kyc", "doc_public"}


def test_wrong_role_never_returns_the_doc():
    store = _store()
    _seed(store)
    # bob: employee only, no compliance_officer / customer_support
    permission = PermissionContext(roles={"employee"}, clearance=1, compartments=set())

    hits = store.search(_embed("KYC/AML 审核标准"), permission, top_k=5)

    assert "doc_kyc" not in {h.doc_id for h in hits}
    assert "doc_support" not in {h.doc_id for h in hits}
    assert {h.doc_id for h in hits} == {"doc_public"}


def test_insufficient_clearance_never_returns_the_doc():
    store = _store()
    _seed(store)
    # has the role, but clearance too low
    permission = PermissionContext(roles={"compliance_officer"}, clearance=1, compartments={"aml"})

    hits = store.search(_embed("KYC/AML 审核标准"), permission, top_k=5)

    assert "doc_kyc" not in {h.doc_id for h in hits}


def test_missing_compartment_never_returns_the_doc():
    store = _store()
    _seed(store)
    # has role + clearance, but not the 'aml' compartment
    permission = PermissionContext(roles={"compliance_officer"}, clearance=2, compartments=set())

    hits = store.search(_embed("KYC/AML 审核标准"), permission, top_k=5)

    assert "doc_kyc" not in {h.doc_id for h in hits}


def test_no_roles_returns_nothing():
    store = _store()
    _seed(store)
    permission = PermissionContext(roles=set(), clearance=4, compartments={"aml"})

    assert store.search(_embed("KYC"), permission, top_k=5) == []


# --- pure-python exhaustive edge cases for the final enforcement layer ---


def test_is_permitted_requires_role_overlap():
    permission = PermissionContext(roles={"employee"}, clearance=4, compartments={"aml", "finance"})
    assert not is_permitted(["compliance_officer"], 1, [], permission)


def test_is_permitted_requires_full_clearance():
    permission = PermissionContext(roles={"compliance_officer"}, clearance=1, compartments=set())
    assert not is_permitted(["compliance_officer"], 2, [], permission)


def test_is_permitted_requires_true_subset_not_mere_overlap():
    # doc requires BOTH aml and finance; user only has aml -> must be denied
    permission = PermissionContext(roles={"compliance_officer"}, clearance=4, compartments={"aml"})
    assert not is_permitted(["compliance_officer"], 1, ["aml", "finance"], permission)


def test_is_permitted_allows_when_all_conditions_met():
    permission = PermissionContext(roles={"compliance_officer"}, clearance=2, compartments={"aml", "finance"})
    assert is_permitted(["compliance_officer"], 2, ["aml"], permission)


def test_filter_hits_drops_everything_disallowed():
    from app.services.vectorstore.base import ScoredChunk

    hits = [
        ScoredChunk("c1", "d1", "t", 0.9, ["compliance_officer"], 2, ["aml"]),
        ScoredChunk("c2", "d2", "t", 0.8, ["employee"], 1, []),
    ]
    permission = PermissionContext(roles={"employee"}, clearance=1, compartments=set())

    result = filter_hits_by_permission(hits, permission)

    assert [h.chunk_id for h in result] == ["c2"]
