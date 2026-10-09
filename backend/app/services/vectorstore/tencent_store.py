"""Tencent Cloud VectorDB adapter (the primary backend per readme.txt /
feedback.txt — Qdrant is the local fallback in qdrant_store.py).

What IS verified here, with zero Tencent Cloud account/credentials, by
tests/test_tencent_adapter.py: the request/response shaping functions below
(_chunks_to_documents, _build_search_filter, _parse_search_response) are
plain Python that only touch the real, already-installed `tcvectordb`
package's pure data classes (Document, Filter) — no network call, so they
run and get checked against the actual SDK code, not a guess at its shape.
Confirmed against the installed SDK source: Collection.search() returns
List[List[Dict]] with 'id'/'score' plus whatever output_fields were
requested — the parsing below matches that.

What is NOT verified: everything that needs a live connection — client
auth, create_database_if_not_exists/create_collection_if_not_exists, and
the actual upsert/search RPCs. Smoke-test those against a real account
before relying on them. Also note Tencent's Filter grammar (In/NotIn/
Include/Exclude/IncludeAll, see tcvectordb.model.document.Filter) has no
"field is empty" or true-subset operator, same limitation as Qdrant's
filter DSL — so the pre-filter below only narrows on roles + clearance;
compartments is enforced exclusively by the Python-level
filter_hits_by_permission(), which is authoritative regardless of backend.
"""

from app.core.config import settings
from app.services.vectorstore.base import PermissionContext, ScoredChunk, VectorChunk
from app.services.vectorstore.rbac_filter import filter_hits_by_permission


def _chunks_to_documents(chunks: list[VectorChunk]) -> list:
    from tcvectordb.model.document import Document

    return [
        Document(
            id=chunk.chunk_id,
            vector=chunk.vector,
            text=chunk.text,
            doc_id=chunk.doc_id,
            allowed_roles=chunk.allowed_roles,
            required_clearance=chunk.required_clearance,
            compartments=chunk.compartments,
            version=chunk.version,
            status=chunk.status,
        )
        for chunk in chunks
    ]


def _build_search_filter(permission: PermissionContext):
    from tcvectordb.model.document import Filter

    roles_expr = Filter.In("allowed_roles", sorted(permission.roles))
    clearance_expr = f"required_clearance <= {permission.clearance}"
    return Filter(roles_expr).And(clearance_expr)


def _parse_peek_score(raw_hits: list[list[dict]]) -> float:
    docs = raw_hits[0] if raw_hits else []
    return docs[0].get("score", 0.0) if docs else 0.0


def _parse_search_response(raw_hits: list[list[dict]], permission: PermissionContext) -> list[ScoredChunk]:
    hits = [
        ScoredChunk(
            chunk_id=str(doc["id"]),
            doc_id=doc["doc_id"],
            text=doc["text"],
            score=doc.get("score", 0.0),
            allowed_roles=doc["allowed_roles"],
            required_clearance=doc["required_clearance"],
            compartments=doc["compartments"],
            version=doc.get("version", "v1"),
            status=doc.get("status", "active"),
        )
        for doc in (raw_hits[0] if raw_hits else [])
    ]

    # same non-negotiable final check as QdrantVectorStore
    return filter_hits_by_permission(hits, permission)


class TencentVectorDBStore:
    def __init__(self, url: str | None = None, collection: str | None = None, dim: int | None = None):
        import tcvectordb
        from tcvectordb.model.enum import FieldType, IndexType, MetricType
        from tcvectordb.model.index import FilterIndex, HNSWParams, Index, VectorIndex

        self._dim = dim or settings.embedding_dim
        self._collection_name = collection or settings.vector_collection_name

        self._client = tcvectordb.RPCVectorDBClient(
            url=url or settings.tencent_vectordb_url,
            username="root",
            key=settings.tencent_vectordb_api_key,
        )
        self._db = self._client.create_database_if_not_exists("rbac_rag")
        self._collection = self._db.create_collection_if_not_exists(
            name=self._collection_name,
            shard=1,
            replicas=0,
            description="RBAC-RAG knowledge chunks",
            index=Index(
                FilterIndex(name="id", field_type=FieldType.String, index_type=IndexType.PRIMARY_KEY),
                VectorIndex(
                    name="vector",
                    dimension=self._dim,
                    index_type=IndexType.HNSW,
                    metric_type=MetricType.COSINE,
                    params=HNSWParams(m=16, efconstruction=200),
                ),
                FilterIndex(name="doc_id", field_type=FieldType.String, index_type=IndexType.FILTER),
                FilterIndex(name="allowed_roles", field_type=FieldType.Array, index_type=IndexType.FILTER),
                FilterIndex(name="required_clearance", field_type=FieldType.Uint64, index_type=IndexType.FILTER),
                FilterIndex(name="compartments", field_type=FieldType.Array, index_type=IndexType.FILTER),
                FilterIndex(name="status", field_type=FieldType.String, index_type=IndexType.FILTER),
            ),
        )

    def upsert(self, chunks: list[VectorChunk]) -> None:
        self._collection.upsert(documents=_chunks_to_documents(chunks), build_index=True)

    def delete_doc(self, doc_id: str) -> None:
        # unverified against a live account, like the rest of the RPC calls here
        from tcvectordb.model.document import Filter

        self._collection.delete(filter=Filter(Filter.In("doc_id", [doc_id])))

    def search(
        self, query_vector: list[float], permission: PermissionContext, top_k: int = 5
    ) -> list[ScoredChunk]:
        if not permission.roles:
            return []

        raw_hits = self._collection.search(
            vectors=[query_vector],
            filter=_build_search_filter(permission),
            limit=top_k,
            output_fields=["doc_id", "text", "allowed_roles", "required_clearance", "compartments", "version", "status"],
        )

        return _parse_search_response(raw_hits, permission)

    def peek_top_hit(self, query_vector: list[float]) -> tuple[float, str | None]:
        raw_hits = self._collection.search(vectors=[query_vector], limit=1, output_fields=["doc_id"])
        docs = raw_hits[0] if raw_hits else []
        return (docs[0].get("score", 0.0), docs[0].get("doc_id")) if docs else (0.0, None)

    def peek_top_score(self, query_vector: list[float]) -> float:
        raw_hits = self._collection.search(vectors=[query_vector], limit=1, output_fields=[])
        return _parse_peek_score(raw_hits)
