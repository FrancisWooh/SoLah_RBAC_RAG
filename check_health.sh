#!/usr/bin/env bash
# Diagnostic script for checking backend health in production
# Usage: bash check_health.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"

echo "===== 1. Container Status ====="
$COMPOSE ps

echo ""
echo "===== 2. Backend Logs (last 50 lines) ====="
$COMPOSE logs backend 2>&1 | cat -v | tail -50

echo ""
echo "===== 3. Health Check ====="
$COMPOSE exec -T backend python -c "import urllib.request;resp=urllib.request.urlopen('http://localhost:8000/health',timeout=5);print(resp.read().decode())" 2>&1 || echo "FAILED: Backend not responding"

echo ""
echo "===== 4. Port Check ====="
$COMPOSE exec -T backend python -c "import socket;s=socket.socket();s.settimeout(2);r=s.connect_ex(('127.0.0.1',8000));print('OPEN' if r==0 else 'CLOSED')" 2>&1 || echo "FAILED"

echo ""
echo "===== 5. Nginx Health (via localhost) ====="
curl -k -s https://localhost/health 2>&1 || echo "FAILED: Nginx not responding"

echo ""
echo "===== Done ====="
