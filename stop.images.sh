#!/usr/bin/env bash
# 停止镜像模式的服务栈。
#
# Usage:
#   ./stop.images.sh            停止 + 删除容器，保留数据卷
#   ./stop.images.sh --purge    停止 + 删除容器 + 清空所有数据卷

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ "${1:-}" == "--purge" ]]; then
  echo "==> --purge：停止并删除容器 + 数据卷（数据库/向量库数据会被清空）"
  docker compose -f docker-compose.images.yml down -v
else
  echo "==> 停止并删除容器（数据卷保留，下次 ./start.images.sh 会接着用）"
  docker compose -f docker-compose.images.yml down
fi

echo "done."
