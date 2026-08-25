# Rabta AI — Production Operations Runbook

A guide for the solo founder to operate and maintain Rabta AI on the production server without guessing.

---

## 1. How to Check If Everything Is Working

### Option A: From Any Browser / Mobile (No Login Needed)
Open: **`https://api.yourdomain.com/health`**
* **Good:** `{"status":"healthy","db":"ok"}`
* **Bad:** Error 502, connection refused, or `{"status":"degraded"}`

### Option B: From the Server Terminal
SSH into your server:
```bash
ssh rabta@<your-server-ip>
```
Run:
```bash
docker compose ps
```
You should see 4 services with `(healthy)` or `running` under the STATUS column:
```text
NAME             IMAGE                  STATUS
rabta_caddy      caddy:2-alpine         Up (healthy)
rabta_backend    rabta-ai-backend       Up (healthy)
rabta_gateway    rabta-ai-gateway       Up (healthy)
rabta_postgres   postgres:16-alpine     Up (healthy)
```

---

## 2. How to View Live Logs (When Diagnosing an Issue)

### View Live Inbound Customer Chats & AI Responses:
```bash
docker compose logs -f --tail=100 backend
```
*(Press `Ctrl + C` anytime to exit log viewing without stopping the app)*

### View WhatsApp Gateway Connection & QR Code Status:
```bash
docker compose logs -f --tail=100 gateway
```

### View Webhook & Web Traffic (Caddy Proxy):
```bash
docker compose logs -f --tail=100 caddy
```

---

## 3. How to Restart Services (When Something Is Stuck)

### Restart the Entire Application Stack:
```bash
cd /opt/rabta
docker compose restart
```

### Restart Only the WhatsApp Gateway (e.g. to re-trigger phone connection):
```bash
docker compose restart gateway
```

### Restart Only the AI Backend:
```bash
docker compose restart backend
```

---

## 4. How to Update Code (Deploying New Features)

Whenever you push new changes to GitHub, deploy them in one command:
```bash
cd /opt/rabta
bash scripts/deploy.sh
```
This script automatically:
1. Pulls the latest code from GitHub
2. Rebuilds the Docker containers
3. Applies any new database migrations
4. Checks that all health checks pass

---

## 5. How to Re-link WhatsApp Phone (If Phone Logs Out)

1. Open your browser to: **`https://api.yourdomain.com/gateway/`**
2. You will see a live QR code on screen.
3. On your business phone:
   * Open **WhatsApp** > **Settings** (or 3 dots) > **Linked Devices** > **Link a Device**
4. Point your phone camera at the screen and scan the QR code.
5. The screen will change to `✅ WhatsApp Connected!`.

---

## 6. How Backups Work & How to Restore

### When Backups Run:
A daily backup runs automatically at 3:00 AM every day and is stored in `/opt/rabta/backups/`.

### Run a Manual Backup Right Now:
```bash
bash /opt/rabta/scripts/backup_db.sh
```

### How to Restore the Database from a Backup:
If data was ever accidentally corrupted or lost:
```bash
# 1. List your available backup files:
ls -lh /opt/rabta/backups/

# 2. Restore from the desired backup file (example):
gunzip -c /opt/rabta/backups/rabta_db_20260826_030000.sql.gz | docker compose exec -T postgres psql -U postgres -d rabta_dev
```

---

## 7. Emergency Troubleshooting Checklist

| Symptom | Cause | Quick Fix |
|---|---|---|
| Customer messages not getting AI replies | Phone was unlinked or disconnected | Visit `https://api.yourdomain.com/gateway/` and re-scan QR code. |
| AI gives generic replies without product prices | Database is down or catalog is empty | Run `docker compose logs backend` to check DB errors. Run `docker compose restart postgres backend`. |
| 502 Bad Gateway error on website | Caddy is running but backend crashed | Run `docker compose logs backend` to see crash reason, then `docker compose restart backend`. |
| Server rebooted unexpectedly | Server power cycle | The stack has `restart: unless-stopped` on all containers — it will automatically be back up within 60 seconds without you doing anything. |
