#!/usr/bin/env bash
# ==============================================================================
# Rabta AI — Automated Database Backup & Off-Server Sync Script
# Runs pg_dump inside Postgres container, compresses with gzip,
# uploads to Cloudflare R2 / AWS S3 via rclone, and prunes local backups > 14 days.
#
# Recommended Cron (every day at 3:00 AM):
# 0 3 * * * /opt/rabta/scripts/backup_db.sh >> /var/log/rabta_backup.log 2>&1
# ==============================================================================

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/rabta}"
BACKUP_DIR="${APP_DIR}/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/rabta_db_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "================================================================="
echo "🗄️ RABTA AI — Starting DB Backup at $(date)"
echo "================================================================="

# Source environment
if [ -f "$APP_DIR/.env" ]; then
    export $(grep -v '^#' "$APP_DIR/.env" | xargs)
fi

DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-rabta_dev}"

# 1. Dump database from Docker container directly to compressed file
echo "📦 Dumping database '${DB_NAME}'..."
docker compose -f "${APP_DIR}/docker-compose.yml" exec -T postgres \
    pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Backup created successfully: ${BACKUP_FILE} (${FILE_SIZE})"

# 2. Upload to Cloudflare R2 / S3 if rclone is configured
if command -v rclone &> /dev/null && [ -n "${R2_BUCKET_NAME:-}" ]; then
    echo "☁️ Uploading backup to Cloudflare R2: r2:${R2_BUCKET_NAME}/backups/..."
    rclone copy "$BACKUP_FILE" "r2:${R2_BUCKET_NAME}/backups/" --fast-list || {
        echo "⚠️ Cloudflare R2 upload failed — check rclone credentials."
    }
fi

# 3. Prune local backups older than 14 days
echo "🧹 Cleaning up local backups older than 14 days..."
find "$BACKUP_DIR" -name "rabta_db_*.sql.gz" -mtime +14 -delete

echo "✅ Backup job finished at $(date)"
echo "================================================================="
