#!/usr/bin/env bash
# Installs (or updates) the cron job that mirrors the COS document library into ./data every 5 minutes.
# Run it once on the VM from the project directory:
#   ./install_cos_sync_cron.sh            install
#   ./install_cos_sync_cron.sh --print    only print the cron line
#   ./install_cos_sync_cron.sh --remove   uninstall
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
DIR="$(pwd)"
LOG="${COS_SYNC_LOG:-$HOME/cos-sync.log}"
MARK="# aspire-cos-sync"
LINE="*/5 * * * * cd $DIR && docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend python sync_data_from_cos.py >> $LOG 2>&1 $MARK"

case "${1:-}" in
  --print)  echo "$LINE"; exit 0 ;;
  --remove) (crontab -l 2>/dev/null | grep -vF "$MARK" || true) | crontab -; echo "removed"; exit 0 ;;
esac

(crontab -l 2>/dev/null | grep -vF "$MARK" || true; echo "$LINE") | crontab -
echo "installed. Every 5 minutes: COS -> $DIR/data   (log: $LOG)"
crontab -l | grep -F "$MARK"
