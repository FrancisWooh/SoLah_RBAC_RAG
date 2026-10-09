"""Exercises the Tencent adapter's request/response shaping against the
REAL installed tcvectordb package (Document, Filter) — these specific
pieces require no network call and no credentials, so this is genuine
verification of our code against the actual SDK, not a guess. What this
does NOT cover: the live RPC calls (auth, create_collection, upsert,
search) in TencentVectorDBStore.__init__/upsert/search — those still need
a real Tencent Cloud account to smoke-test, see tencent_store.py docstring.
"""

from app.services.vectorstore.base import PermissionContext, VectorChunk
from app.services.vectorstore.tencent_store import (
    _build_search_filter,
    _chunks_to_documents,
    _parse_search_response,
)


def test_chunks_to_documents_uses_real_sdk_document_class():
    from tcvectordb.model.document import Document

    chunk = VectorChunk(
        chunk_id="doc_a::chunk0",
        doc_id="doc_a",
        text="hello",
        vector=[0.1, 0.2],
        allowed_roles=["compliance_officer"],
        required_clearance=2,
        compartments=["aml"],
    )

    docs = _chunks_to_documents([chunk])

    assert len(docs) == 1
    assert isinstance(docs[0], Document)
    assert docs[0].__dict__["id"] == "doc_a::chunk0"
    assert docs[0].__dict__["allowed_roles"] == ["compliance_officer"]
    assert docs[0].__dict__["required_clearance"] == 2


def test_build_search_filter_produces_expected_expression():
    permission = PermissionContext(roles={"compliance_officer"}, clearance=2, compartments={"aml"})

    filt = _build_search_filter(permission)

    assert filt.cond == '(allowed_roles in ("compliance_officer")) and (required_clearance <= 2)'


def test_build_search_filter_sorts_multiple_roles_deterministically():
    permission = PermissionContext(roles={"card_ops", "compliance_officer"}, clearance=1, compartments=set())

    filt = _build_search_filter(permission)

    assert filt.cond == (
        '(allowed_roles in ("card_ops","compliance_officer")) and (required_clearance <= 1)'
    )


def _raw_response(docs: list[dict]) -> list[list[dict]]:
    return [docs]  # one inner list per query vector, per the real SDK's search() signature


def test_parse_search_response_maps_fields_and_still_enforces_rbac():
    permission = PermissionContext(roles={"compliance_officer"}, clearance=2, compartments={"aml"})
    raw = _raw_response(
        [
            {
                "id": "doc_a::chunk0",
                "score": 0.87,
                "doc_id": "doc_a",
                "text": "hello",
                "allowed_roles": ["compliance_officer"],
                "required_clearance": 2,
                "compartments": ["aml"],
            },
            {
                # a hit Tencent's pre-filter let through (e.g. compartments
                # overlap but isn't a true subset) must still be dropped here
                "id": "doc_b::chunk0",
                "score": 0.91,
                "doc_id": "doc_b",
                "text": "secret",
                "allowed_roles": ["compliance_officer"],
                "required_clearance": 2,
                "compartments": ["aml", "finance"],
            },
        ]
    )

    result = _parse_search_response(raw, permission)

    assert [r.doc_id for r in result] == ["doc_a"]
    assert result[0].score == 0.87


def test_parse_search_response_handles_empty_results():
    permission = PermissionContext(roles={"compliance_officer"}, clearance=2, compartments={"aml"})
    assert _parse_search_response([], permission) == []
    assert _parse_search_response([[]], permission) == []
