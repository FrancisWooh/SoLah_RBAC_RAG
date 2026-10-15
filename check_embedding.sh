#!/usr/bin/env bash
# Verify embedding model and dimension are correct after deployment
# Usage: bash check_embedding.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"

echo "===== 1. Embedding Config (from .env) ====="
echo "  EMBEDDING_BACKEND: $(grep -E '^EMBEDDING_BACKEND=' backend/.env 2>/dev/null | cut -d= -f2 || echo 'not set (default=mock)')"
echo "  LOCAL_EMBEDDING_MODEL: $(grep -E '^LOCAL_EMBEDDING_MODEL=' backend/.env 2>/dev/null | cut -d= -f2 || echo 'not set (default=Qwen/Qwen3-Embedding-0.6B)')"
echo "  EMBEDDING_DIM: $(grep -E '^EMBEDDING_DIM=' backend/.env 2>/dev/null | cut -d= -f2 || echo 'not set (default=1024)')"

echo ""
echo "===== 2. Settings Loaded by Backend ====="
$COMPOSE exec -T backend python -c "
from app.core.config import settings
print(f'  embedding_backend: {settings.embedding_backend}')
print(f'  local_embedding_model: {settings.local_embedding_model}')
print(f'  embedding_dim: {settings.embedding_dim}')
" 2>&1

echo ""
echo "===== 3. Actual Embedding Test ====="
$COMPOSE exec -T backend python -c "
from app.services.embeddings.factory import get_embedder
e = get_embedder()
print(f'  model: {e._inner.model_name}')
print(f'  dim: {e.dim}')
print(f'  is_asymmetric: {getattr(e._inner, \"_is_asymmetric\", False)}')
vec = e.embed_query('test query for dimension check')
print(f'  query vector length: {len(vec)}')
print(f'  first 5 values: {vec[:5]}')
print('  OK: Embedding works correctly')
" 2>&1

echo ""
echo "===== 4. Qdrant Collection Dimension ====="
$COMPOSE exec -T backend python -c "
from qdrant_client import QdrantClient
import os
url = os.getenv('QDRANT_URL', 'http://qdrant:6333')
c = QdrantClient(url=url)
try:
    info = c.get_collection('knowledge_chunks')
    print(f'  collection: knowledge_chunks')
    print(f'  vector dim: {info.config.params.vectors.size}')
    print(f'  points: {info.points_count}')
except Exception as e:
    print(f'  WARN: {e}')
" 2>&1

echo ""
echo "===== Done ====="
