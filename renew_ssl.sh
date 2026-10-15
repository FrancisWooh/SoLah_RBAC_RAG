#!/usr/bash
# Let's Encrypt auto-renewal script for aspire.5gbulab.tech
# Runs via crontab, renews cert, copies to nginx/ssl, restarts nginx.
set -euo pipefail

PROJECT_DIR="/home/ubuntu/SoLah_RBAC_RAG"
DOMAIN="aspire.5gbulab.tech"

cd "$PROJECT_DIR"

# Renew cert (standalone mode needs port 80, so stop nginx first)
docker compose -f docker-compose.prod.yml --env-file .env.prod stop nginx

sudo certbot renew --standalone --quiet

# Copy renewed certs
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/fullchain.pem
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/privkey.pem

# Restart nginx
docker compose -f docker-compose.prod.yml --env-file .env.prod start nginx

echo "[$(date)] SSL cert renewed successfully" >> /var/log/ssl-renew.log
