from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Aspire Internal Brain"
    environment: str = "dev"

    database_url: str = "postgresql+psycopg2://rbac:rbac@postgres:5432/rbac_rag"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    vector_backend: str = "qdrant"  # "tencent_vectordb" | "qdrant"
    qdrant_url: str = "http://qdrant:6333"
    vector_collection_name: str = "knowledge_chunks"

    llm_backend: str = "mock"  # "anthropic" | "openai_compat" | "hunyuan" | "deepseek" | "mock"
    llm_base_url: str = "https://tokenhub-intl.tencentcloudmaas.com/v1"
    llm_model: str = "hy3"
    llm_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_workspace_id: str = ""  # required when the API key is not scoped to a workspace
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_effort: str = "low"  # low | medium | high | xhigh | max
    hunyuan_model: str = "hunyuan-turbos-latest"
    deepseek_base_url: str = "http://localhost:8001/v1"
    deepseek_model: str = "deepseek-r1-distill-qwen-14b"
    deepseek_api_key: str = ""
    embedding_backend: str = "mock"  # "local" | "hunyuan" | "mock"
    local_embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_cache_path: str = ".embed_cache.sqlite"
    embedding_batch_size: int = 4  # texts per local-embedder forward pass; lower = less peak RAM, slower ingestion
    embedding_max_seq_length: int = 1024  # tokens kept per text (table chunks reach ~950); lower = less RAM but truncates
    retrieve_k: int = 10  # candidates fetched from the vector store
    serve_floor: float = 0.40  # chunks down to this score may fill the context once the query clears relevance_threshold
    serve_k: int = 5  # best candidates (above the relevance bar) given to the LLM
    neighbor_top: int = 2  # also give the neighbouring chunks of this many top hits (0 = off)
    neighbor_window: int = 1  # chunks before/after each of those hits
    deny_margin: float = 0.12  # see query_service.DENY_MARGIN
    deny_strong_score: float = 0.58  # see query_service.DENY_STRONG_SCORE
    relevance_threshold: float = 0.20  # calibrate per embedder, see query_service.py
    data_dir: str = "/data"  # document library root (manifest.json + files)
    library_sync_interval: int = 30  # seconds between scans of data_dir for changed files; 0 disables
    db_sync_interval: int = 30  # seconds between syncs of the registered department databases (data_sources); 0 disables
    embedding_dim: int = 1024  # matches hunyuan-embedding so swapping backends needs no collection rebuild

    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_vectordb_url: str = ""
    tencent_vectordb_api_key: str = ""
    hunyuan_embedding_url: str = ""

    ocr_backend: str = "tesseract"  # "tencent" | "tesseract"

    idp_provider: str = "mock"  # "mock" | "oidc" | "saml"
    idp_group_role_map_path: str = ""  # optional JSON file for group->role mapping; empty = built-in defaults


settings = Settings()
