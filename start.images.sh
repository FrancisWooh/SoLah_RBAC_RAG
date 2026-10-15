#!/usr/bin/env bash
# 从 Docker Hub 拉取预构建镜像并启动完整服务栈。
# 镜像来源: fancylan/so-lah-rbac-rag:{backend,frontend}
#
# Usage:
#   ./start.images.sh            拉取镜像 + 启动 + 迁移 + 种子数据（仅 DB 为空时）
#   ./start.images.sh --reset    清空数据卷 + 重新拉取镜像 + 全新种子数据

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

# --- 1. 拉取镜像 ---
echo "==> 从 Docker Hub 拉取镜像（fancylan/so-lah-rbac-rag）"
docker pull fancylan/so-lah-rbac-rag:backend
docker pull fancylan/so-lah-rbac-rag:frontend

# --- 2. 启动 / 重置 ---
if $RESET; then
  echo "==> --reset：清空容器和数据卷"
  docker compose -f docker-compose.images.yml down -v
fi

echo "==> 启动 docker compose（使用预构建镜像，不再本地 build）"
docker compose -f docker-compose.images.yml up -d

# --- 3. 等待后端就绪 ---
echo "==> 等待后端 /health 就绪"
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "    后端已就绪"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "错误：后端 60 秒内未就绪，请用 'docker compose -f docker-compose.images.yml logs backend' 排查。" >&2
    exit 1
  fi
  sleep 1
done

# --- 4. 数据库迁移 ---
echo "==> 执行数据库 migration"
docker compose -f docker-compose.images.yml exec -T backend alembic upgrade head

# --- 5. 种子数据（仅首次） ---
USER_COUNT=$(docker compose -f docker-compose.images.yml exec -T postgres psql -U rbac -d rbac_rag -tAc "select count(*) from users;" 2>/dev/null || echo 0)
USER_COUNT=$(echo "$USER_COUNT" | tr -d '[:space:]')

if [[ "$USER_COUNT" == "0" ]]; then
  echo "==> 数据库为空，写入种子数据（用户/角色/文档 + 向量库 + 审计历史 + 哈希链；首次向量化在 CPU 上约需 20 分钟）"
  docker compose -f docker-compose.images.yml exec -T backend python seed_data.py
  docker compose -f docker-compose.images.yml exec -T backend python seed_vectorstore.py
  docker compose -f docker-compose.images.yml exec -T backend python seed_audit_history.py
  docker compose -f docker-compose.images.yml exec -T backend python backfill_audit_hash_chain.py
else
  echo "==> 数据库已有数据（$USER_COUNT 个用户），跳过种子数据（用 --reset 可强制重置）"
fi

cat <<'EOF'

==================== 启动完成（镜像模式） ====================
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

查看日志: docker compose -f docker-compose.images.yml logs -f backend
停止服务: ./stop.images.sh
==============================================================
EOF
