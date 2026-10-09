#!/usr/bin/env bash
# Stops the stack. By default keeps data (named volumes: pgdata, qdrant_data)
# so the next ./start.sh picks up right where you left off.
#
# Usage:
#   ./stop.sh            stop + remove containers, keep data
#   ./stop.sh --purge    stop + remove containers AND delete all data volumes

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ "${1:-}" == "--purge" ]]; then
  echo "==> --purge：停止并删除容器 + 数据卷（数据库/向量库数据会被清空）"
  docker compose down -v
else
  echo "==> 停止并删除容器（数据卷保留，下次 ./start.sh 会接着用）"
  docker compose down
fi

echo "done."
