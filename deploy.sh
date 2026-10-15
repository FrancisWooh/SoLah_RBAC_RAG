#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Production deployment for Aspire Internal Brain
#
# Prerequisites:
#   - Docker + Docker Compose installed
#   - backend/.env configured (JWT_SECRET, LLM_API_KEY, etc.)
#   - frontend/.env configured (VITE_API_BASE_URL)
#   - .env.prod configured (PUBLIC_URL, POSTGRES_PASSWORD, etc.)
#   - SSL certs placed in nginx/ssl/ (fullchain.pem + privkey.pem)
#
# Usage:
#   ./deploy.sh              First-time deploy (pull + up + migrate + seed)
#   ./deploy.sh --reset      Wipe data and re-deploy from scratch
#   ./deploy.sh --ssl-only    Generate Let's Encrypt cert (needs certbot)
#   ./deploy.sh --rebuild     Pull latest images and restart
# =============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

COMPOSE="docker compose -f docker-compose.prod.yml"

# --- Parse args ---
RESET=false
SSL_ONLY=false
REBUILD=false
for arg in "$@"; do
  case $arg in
    --reset)   RESET=true ;;
    --ssl-only) SSL_ONLY=true ;;
    --rebuild) REBUILD=true ;;
  esac
done

# --- Check prerequisites ---
echo "==> Checking prerequisites"

if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Copy backend/.env.example and configure it."
  exit 1
fi

if [ ! -f .env.prod ]; then
  echo "ERROR: .env.prod not found. Copy .env.prod.example and configure it."
  exit 1
fi

# --- SSL certificate ---
if [ ! -f nginx/ssl/fullchain.pem ] || [ ! -f nginx/ssl/privkey.pem ]; then
  echo "WARNING: SSL certs not found in nginx/ssl/"
  echo "  Option 1: Place fullchain.pem + privkey.pem in nginx/ssl/"
  echo "  Option 2: Run ./deploy.sh --ssl-only to generate self-signed certs"
  echo "  Option 3: Use Let's Encrypt after first boot (see README_EN.md)"
  echo ""

  if [ "$SSL_ONLY" = true ]; then
    echo "==> Generating self-signed SSL certificate (for testing only)"
    mkdir -p nginx/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout nginx/ssl/privkey.pem \
      -out nginx/ssl/fullchain.pem \
      -subj "/CN=aspire.5gbulab.tech"
    echo "    Self-signed cert generated (365 days). Replace with real cert for production."
    exit 0
  fi

  echo "  Continuing without SSL... (Nginx may fail to start)"
  echo ""
fi

# --- Reset ---
if [ "$RESET" = true ]; then
  echo "==> --reset: wiping containers and data volumes"
  $COMPOSE --env-file .env.prod down -v
fi

# --- Rebuild (pull latest images) ---
if [ "$REBUILD" = true ]; then
  echo "==> --rebuild: pulling latest images"
  $COMPOSE --env-file .env.prod pull
  $COMPOSE --env-file .env.prod up -d
  echo "==> Done. Services restarted."
  exit 0
fi

# --- Start ---
echo "==> Starting services"
$COMPOSE --env-file .env.prod up -d

# --- Wait for backend health ---
echo "==> Waiting for backend /health"
for i in $(seq 1 120); do
  if $COMPOSE exec -T backend python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then
    echo "    Backend ready"
    break
  fi
  if [ $i -eq 120 ]; then
    echo "ERROR: Backend not ready within 120s. Check: $COMPOSE logs backend"
    exit 1
  fi
  sleep 1
done

# --- Database migration ---
echo "==> Running database migration"
$COMPOSE exec -T backend alembic upgrade head

# --- Seed data (only if DB is empty) ---
USER_COUNT=$($COMPOSE exec -T postgres psql \
  -U "${POSTGRES_USER:-rbac}" -d "${POSTGRES_DB:-rbac_rag}" \
  -tAc "select count(*) from users;" 2>/dev/null || echo 0)
USER_COUNT=$(echo "$USER_COUNT" | tr -d '[:space:]')

if [ "$USER_COUNT" = "0" ]; then
  echo "==> Database empty, seeding data (first-time vectorization ~10-20 min on 4-core)"
  $COMPOSE exec -T backend python seed_data.py
  $COMPOSE exec -T backend python seed_vectorstore.py
  $COMPOSE exec -T backend python seed_audit_history.py
  $COMPOSE exec -T backend python backfill_audit_hash_chain.py
  echo "    Seeding complete"
else
  echo "==> Database has $USER_COUNT users, skipping seed"
fi

# --- Done ---
source .env.prod 2>/dev/null || true
PUBLIC_URL="${PUBLIC_URL:-https://aspire.5gbulab.tech}"

cat <<EOF

==================== Deployment Complete ====================
Frontend:   ${PUBLIC_URL}
Admin:      ${PUBLIC_URL}:443  (via admin.* subdomain)
API docs:   ${PUBLIC_URL}/docs
Health:     ${PUBLIC_URL}/health

Login:      Visit frontend, select a mock SSO account

Logs:       $COMPOSE logs -f backend
Stop:       $COMPOSE down
Restart:    $COMPOSE restart
Full reset: ./deploy.sh --reset
==============================================================
EOF
