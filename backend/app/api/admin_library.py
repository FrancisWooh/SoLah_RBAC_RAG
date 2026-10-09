from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.api.deps import require_roles
from app.models.user import User
from app.services.db_sync import run_db_sync
from app.services.library_sync import run_sync

router = APIRouter()


@router.post("/sync")
async def sync_now(_current_user: User = Depends(require_roles("platform_admin"))):
    """Scan the document library now and bring the knowledge base up to date."""
    r = await run_in_threadpool(run_sync)
    return {"added": r.added, "updated": r.updated, "archived": r.archived,
            "removed": r.removed, "skipped": r.skipped, "errors": r.errors}


@router.post("/db-sync")
async def db_sync_now(source_id: int | None = None, _current_user: User = Depends(require_roles("platform_admin"))):
    """Read the registered department databases now and bring the knowledge base up to date
    (all sources, or just `source_id`)."""
    results = await run_in_threadpool(run_db_sync, source_id)
    return {"sources": {name: {"added": r.added, "updated": r.updated, "archived": r.archived,
                               "removed": r.removed, "skipped": r.skipped, "errors": r.errors}
                        for name, r in results.items()}}
