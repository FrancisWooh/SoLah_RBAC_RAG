import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import settings
from app.services.vectorstore.base import BlindHit, PermissionContext, ScoredChunk, VectorChunk
from app.services.vectorstore.rbac_filter import filter_hits_by_permission


class QdrantVectorStore:
    """Local/self-hosted fallback for Tencent Cloud VectorDB (same interface
    as TencentVectorDBStore, see tencent_store.py)."""

    def __init__(self, url: str | None = None, collection: str | None = None, dim: int | None = None):
        self._client = QdrantClient(url=url or settings.qdrant_url)
        self._collection = collection or settings.vector_collection_name
        self._dim = dim or settings.embedding_dim
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self._client.collection_exists(self._collection):
            self._client.create_payload_index(self._collection, "status", qm.PayloadSchemaType.KEYWORD)
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qm.VectorParams(size=self._dim, distance=qm.Distance.COSINE),
        )
        self._client.create_payload_index(self._collection, "allowed_roles", qm.PayloadSchemaType.KEYWORD)
        self._client.create_payload_index(self._collection, "compartments", qm.PayloadSchemaType.KEYWORD)
        self._client.create_payload_index(self._collection, "required_clearance", qm.PayloadSchemaType.INTEGER)
        self._client.create_payload_index(self._collection, "status", qm.PayloadSchemaType.KEYWORD)

    def reset(self) -> None:
        """Drop and recreate the collection (used by re-seeding so chunks of
        removed/shrunk documents don't linger)."""
        if self._client.collection_exists(self._collection):
            self._client.delete_collection(self._collection)
        self._ensure_collection()

    @staticmethod
    def _not_archived() -> list[qm.Condition]:
        # must_not (rather than must status==active) so legacy points that
        # have no status payload are still treated as active.
        return [qm.FieldCondition(key="status", match=qm.MatchAny(any=["archived", "deleted"]))]

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        # Qdrant point ids must be an unsigned int or a UUID, so our
        # human-readable "doc_id::chunk_n" ids go in as a payload field
        # (chunk_ref) and get mapped to a deterministic UUID here.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

    def upsert(self, chunks: list[VectorChunk]) -> None:
        points = [
            qm.PointStruct(
                id=self._point_id(chunk.chunk_id),
                vector=chunk.vector,
                payload={
                    "chunk_ref": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "allowed_roles": chunk.allowed_roles,
                    "required_clearance": chunk.required_clearance,
                    "compartments": chunk.compartments,
                    "version": chunk.version,
                    "status": chunk.status,
                },
            )
            for chunk in chunks
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def delete_doc(self, doc_id: str) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))])
            ),
        )

    def search(
        self, query_vector: list[float], permission: PermissionContext, top_k: int = 5
    ) -> list[ScoredChunk]:
        if not permission.roles:
            return []

        must: list[qm.Condition] = [
            qm.FieldCondition(key="allowed_roles", match=qm.MatchAny(any=sorted(permission.roles))),
            qm.FieldCondition(key="required_clearance", range=qm.Range(lte=permission.clearance)),
        ]

        compartment_should: list[qm.Condition] = [
            qm.IsEmptyCondition(is_empty=qm.PayloadField(key="compartments"))
        ]
        if permission.compartments:
            compartment_should.append(
                qm.FieldCondition(key="compartments", match=qm.MatchAny(any=sorted(permission.compartments)))
            )
        must.append(qm.Filter(should=compartment_should))

        results = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=qm.Filter(must=must, must_not=self._not_archived()),
            limit=top_k,
        ).points

        hits = [
            ScoredChunk(
                chunk_id=r.payload.get("chunk_ref", str(r.id)),
                doc_id=r.payload["doc_id"],
                text=r.payload["text"],
                score=r.score,
                allowed_roles=r.payload["allowed_roles"],
                required_clearance=r.payload["required_clearance"],
                compartments=r.payload["compartments"],
                version=r.payload.get("version", "v1"),
                status=r.payload.get("status", "active"),
            )
            for r in results
        ]

        # Qdrant's filter above is a performance pre-filter (exact for roles
        # and clearance, "overlap-or-empty" approximation for compartments).
        # This is the real, exact, never-bypassed guarantee.
        return filter_hits_by_permission(hits, permission)

    def get_chunks(self, chunk_ids: list[str], permission: PermissionContext) -> list[ScoredChunk]:
        if not chunk_ids or not permission.roles:
            return []
        records = self._client.retrieve(
            collection_name=self._collection,
            ids=[self._point_id(c) for c in chunk_ids],
            with_payload=True,
        )
        hits = [
            ScoredChunk(
                chunk_id=r.payload.get("chunk_ref", str(r.id)),
                doc_id=r.payload["doc_id"],
                text=r.payload["text"],
                score=0.0,
                allowed_roles=r.payload["allowed_roles"],
                required_clearance=r.payload["required_clearance"],
                compartments=r.payload["compartments"],
                version=r.payload.get("version", "v1"),
                status=r.payload.get("status", "active"),
            )
            for r in records
        ]
        return filter_hits_by_permission(hits, permission)

    def peek_top_hit(self, query_vector: list[float]) -> tuple[float, str | None]:
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=qm.Filter(must_not=self._not_archived()),
            limit=1,
            with_payload=["doc_id"],
        ).points
        return (results[0].score, results[0].payload.get("doc_id")) if results else (0.0, None)

    def peek_top_score(self, query_vector: list[float]) -> float:
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=qm.Filter(must_not=self._not_archived()),
            limit=1,
        ).points
        return results[0].score if results else 0.0

    def peek_relevant_hits(
        self, query_vector: list[float], top_k: int = 10
    ) -> list[BlindHit]:
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=qm.Filter(must_not=self._not_archived()),
            limit=top_k,
            with_payload=["doc_id", "allowed_roles", "required_clearance",
                           "compartments", "status"],
        ).points
        return [
            BlindHit(
                doc_id=r.payload.get("doc_id", ""),
                score=r.score,
                allowed_roles=r.payload.get("allowed_roles", []),
                required_clearance=r.payload.get("required_clearance", 0),
                compartments=r.payload.get("compartments", []),
                status=r.payload.get("status", "active"),
            )
            for r in results
        ]
