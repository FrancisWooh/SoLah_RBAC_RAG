import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_audit import router as admin_audit_router
from app.api.admin_dashboard import router as admin_dashboard_router
from app.api.admin_library import router as admin_library_router
from app.api.admin_roles import router as admin_roles_router
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.query import router as query_router
from app.api.role_requests import router as role_requests_router
from app.api.roles import router as roles_router
from app.core.config import settings
from app.mcp_server import mcp_app


logger = logging.getLogger(__name__)


def _warm_up() -> None:
    """Load the embedding model and open the vector store in the background at
    startup, so the first user query doesn't pay the multi-second cold start."""
    try:
        from app.services.embeddings.factory import get_embedder
        from app.services.vectorstore.factory import get_vector_store

        embedder = get_embedder()
        embed_query = getattr(embedder, "embed_query", None)
        embed_query("warm up") if embed_query else embedder.embed_texts(["warm up"])
        get_vector_store()
    except Exception:
        logger.warning("startup warm-up failed (first query will be slower)", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.db_sync import start_db_watcher
    from app.services.library_sync import start_library_watcher

    start_library_watcher()
    start_db_watcher()
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()
    # FastMCP's streamable-http transport needs its session manager's
    # context active for the lifetime of the app — mounting the sub-app
    # alone does not reliably forward ASGI lifespan events to it.
    async with mcp_app.session_manager.run():
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(query_router, prefix="/api/query", tags=["query"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(admin_roles_router, prefix="/api/admin", tags=["admin-roles"])
app.include_router(admin_audit_router, prefix="/api/admin/audit", tags=["admin-audit"])
app.include_router(admin_dashboard_router, prefix="/api/admin/dashboard", tags=["admin-dashboard"])
app.include_router(admin_library_router, prefix="/api/admin/library", tags=["admin-library"])
app.include_router(role_requests_router, prefix="/api/role-requests", tags=["role-requests"])
app.include_router(roles_router, prefix="/api/roles", tags=["roles"])

app.mount("/mcp", mcp_app.streamable_http_app())
