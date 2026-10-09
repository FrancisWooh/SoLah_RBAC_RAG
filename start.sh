#!/usr/bin/env bash
# Brings the whole stack up: docker compose (postgres/redis/qdrant/backend/
# frontend) -> wait for backend health -> run migrations -> seed demo data
# (only if the database is empty, so re-running this doesn't wipe anything
# you did through the UI) -> print URLs and demo accounts.
#
# Usage:
#   ./start.sh            start (seed only if DB is empty)
#   ./start.sh --reset    full wipe (docker compose down -v) + fresh seed

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

RESET=false
if [[ "${1:-}" == "--reset" ]]; then
  RESET=true
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "错误：找不到 docker compose，请先安装 Docker。" >&2
  exit 1
fi

if $RESET; then
  echo "==> --reset：清空容器和数据卷"
  docker compose down -v
fi

echo "==> 启动 docker compose（postgres/redis/qdrant/backend/frontend）"
docker compose up -d --build

echo "==> 等待后端 /health 就绪"
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "    后端已就绪"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "错误：后端 60 秒内未就绪，请用 'docker compose logs backend' 排查。" >&2
    exit 1
  fi
  sleep 1
done

echo "==> 执行数据库 migration"
docker compose exec -T backend alembic upgrade head

USER_COUNT=$(docker compose exec -T postgres psql -U rbac -d rbac_rag -tAc "select count(*) from users;" 2>/dev/null || echo 0)
USER_COUNT=$(echo "$USER_COUNT" | tr -d '[:space:]')

if [[ "$USER_COUNT" == "0" ]]; then
  echo "==> 数据库为空，写入种子数据（用户/角色/文档 + 向量库 + 一周审计历史 + 审计哈希链；首次向量化在 CPU 上约需 20 分钟）"
  docker compose exec -T backend python seed_data.py
  docker compose exec -T backend python seed_vectorstore.py
  docker compose exec -T backend python seed_audit_history.py
  docker compose exec -T backend python backfill_audit_hash_chain.py
else
  echo "==> 数据库已有数据（$USER_COUNT 个用户），跳过种子数据（用 --reset 可强制重置）"
fi

cat <<'EOF'

==================== 启动完成 ====================
前端:        http://localhost:5173
管理后台:      http://localhost:5174
后端 API:    http://localhost:8000
API 文档:    http://localhost:8000/docs
pgAdmin:     http://localhost:5050  (免登录，已预注册连接；密码 rag_reader / rbac)
MCP (只读):  http://localhost:8000/mcp  (需管理员 JWT)

演示账号（模拟 SSO，/login 页面直接选）:
  alice  — compliance_officer (密级2, aml)      carol — compliance_officer + mlro (密级3)
  bob    — engineer (密级2)                    dave  — risk_analyst      erin — card_ops
  frank  — customer_support                    gina  — finance_analyst   henry — hr_manager
  ivy    — marketing_manager                   jack  — account_manager   kate — security_engineer
  leo    — legal_counsel                       vera  — exec (密级4)      admin — platform_admin
  （文档/账号权限矩阵见 requirement/doc_permission_matrix.md）

查看日志: docker compose logs -f backend
停止服务: ./stop.sh
===================================================
EOF
