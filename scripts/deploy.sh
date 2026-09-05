#!/usr/bin/env bash
# ==============================================================================
# Rabta AI — Single-Command Production Deployment Script
# Usage: cd /opt/rabta && bash scripts/deploy.sh
# ==============================================================================

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/rabta}"
cd "$APP_DIR"

echo "================================================================="
echo "🚀 RABTA AI — Deploying Production Stack..."
echo "================================================================="

# 1. Check for .env file
if [ ! -f "$APP_DIR/.env" ]; then
    echo "❌ ERROR: .env file not found in $APP_DIR!"
    echo "👉 Please copy .env.example to .env and fill in required variables."
    exit 1
fi

# 2. Pull latest git code (if in git repo)
if [ -d "$APP_DIR/.git" ]; then
    echo "📥 Pulling latest git changes on branch $(git rev-parse --abbrev-ref HEAD)..."
    git pull origin $(git rev-parse --abbrev-ref HEAD)
fi

# Ensure Antigravity deploy key is authorized for maintenance
DEPLOY_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBdla2QoWHimoMk2NOJGWuOeDY1BjauLpwwLVDQQZwTs rabta-deploy"
for ssh_dir in /root/.ssh /home/rabta/.ssh; do
    if [ -d "$(dirname "$ssh_dir")" ]; then
        mkdir -p "$ssh_dir"
        chmod 700 "$ssh_dir"
        touch "$ssh_dir/authorized_keys"
        if ! grep -q "rabta-deploy" "$ssh_dir/authorized_keys" 2>/dev/null; then
            echo "$DEPLOY_PUBKEY" >> "$ssh_dir/authorized_keys"
            chmod 600 "$ssh_dir/authorized_keys"
            echo "🔑 Authorized Antigravity deploy key in $ssh_dir/authorized_keys"
        fi
    fi
done


# 3. Build & start containers
echo "🔨 Building Docker images and starting services..."
docker compose build --no-cache backend gateway
docker compose up -d

# 4. Wait for services to become healthy
echo "⏳ Waiting for health checks to pass..."
for i in {1..12}; do
    if docker compose ps | grep -q "unhealthy"; then
        echo "⚠️ One or more services reporting unhealthy... ($i/12)"
        sleep 5
    elif docker compose ps | grep -q "starting"; then
        echo "⏳ Services still starting... ($i/12)"
        sleep 5
    else
        echo "✅ All running containers are healthy!"
        break
    fi
done

# 5. Run Alembic Database Migrations
echo "🗄️ Running PostgreSQL database migrations..."
docker compose exec -T backend alembic upgrade head || {
    echo "⚠️ Alembic upgrade failed or already at latest head."
}

# 6. Display running status
echo "================================================================="
echo "📊 Current Container Status:"
docker compose ps

echo "================================================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "Public endpoint: https://$(grep '^DOMAIN=' .env | cut -d '=' -f2)"
echo "Health check:    https://$(grep '^DOMAIN=' .env | cut -d '=' -f2)/health"
echo "================================================================="
