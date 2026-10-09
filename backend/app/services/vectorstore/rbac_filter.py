"""The one authoritative answer to "is this chunk allowed for this user".

Vector-store-level filters (see qdrant_store.py) are a performance
pre-filter, not the source of truth: Qdrant can express "roles overlap" and
"clearance <= X" exactly, but a true subset check for compartments against a
dynamic per-user list doesn't map onto Qdrant's filter DSL for the general
(multi-compartment) case. So every hit, from every backend, is re-checked
here in plain Python before it is allowed to reach the LLM or the API
response. This function must never be bypassed.
"""

from app.services.vectorstore.base import PermissionContext, ScoredChunk


def is_permitted(
    allowed_roles: list[str],
    required_clearance: int,
    compartments: list[str],
    permission: PermissionContext,
) -> bool:
    if not (set(allowed_roles) & permission.roles):
        return False
    if required_clearance > permission.clearance:
        return False
    if not set(compartments).issubset(permission.compartments):
        return False
    return True


def filter_hits_by_permission(
    hits: list[ScoredChunk], permission: PermissionContext
) -> list[ScoredChunk]:
    # Version governance: only "active" documents are retrievable. Archived /
    # deleted versions stay in the store (audit, rollback) but never reach an
    # answer, regardless of backend.
    return [
        hit
        for hit in hits
        if hit.status == "active"
        and is_permitted(hit.allowed_roles, hit.required_clearance, hit.compartments, permission)
    ]
