# Rabta AI — Production System Architecture

```mermaid
flowchart TD
    subgraph Internet ["🌐 Public Internet"]
        Customer["📱 WhatsApp Customer"]
        Merchant["💻 Store Owner / Web Browser"]
        UptimeMonitor["📡 External Uptime Monitor (UptimeRobot)"]
    end

    subgraph Host ["🖥️ Vultr Cloud Compute (Ubuntu 24.04 LTS — Mumbai/Singapore)"]
        subgraph Edge ["Edge Layer (Ports 80 & 443)"]
            Caddy["🔒 Caddy Reverse Proxy<br/>• Auto Let's Encrypt TLS<br/>• HTTPS on :443<br/>• Security Headers"]
        end

        subgraph DockerNetwork ["🐳 Docker Internal Bridge Network (rabta_internal)"]
            subgraph AppLayer ["App Services (restart: unless-stopped)"]
                Gateway["⚡ WhatsApp QR Gateway (Node.js/Baileys :3001)<br/>• Socket link to WhatsApp Web<br/>• Media Download (Photos/Voice)<br/>• Auth Session Volume Mount"]
                Backend["🧠 AI Backend Core (FastAPI :8000)<br/>• Multimodal Store Agent<br/>• Owner Copilot & Commands<br/>• Business Onboarding API<br/>• DB Health Check /health"]
            end

            subgraph DataLayer ["Database Layer (restart: unless-stopped)"]
                Postgres[("🗄️ PostgreSQL 16 (:5432)<br/>• Tenants & Permissions<br/>• 114+ Products Catalog<br/>• Conversations & Messages<br/>• Visual Search Logs<br/>• Named Volume: postgres_data")]
            end
        end

        subgraph HostCron ["⏰ Scheduled Host Jobs"]
            BackupJob["📦 Daily DB Backup (backup_db.sh)<br/>• pg_dump -> gzip<br/>• 14-Day Prune"]
            AutoPatch["🔄 Unattended Security Upgrades"]
        end
    end

    subgraph ExternalCloud ["☁️ External Cloud Services"]
        Gemini["🤖 Google AI Studio (Gemini 3.5 Flash-Lite / Vision)"]
        Deepgram["🎙️ Deepgram SDK (Voice Note Transcription)"]
        MetaAPI["📱 Meta WhatsApp Cloud API / 360dialog (Optional Direct Webhook)"]
        CloudflareR2["💾 Cloudflare R2 / S3 (Encrypted Off-Server Backups)"]
    end

    %% Customer Inbound Flow (Baileys)
    Customer -->|WhatsApp Chat / Images / Voice| Gateway
    Gateway -->|Forward Media & Text HTTP POST| Backend

    %% Web / Webhook Flows
    Merchant -->|HTTPS :443| Caddy
    MetaAPI -.->|Webhook POST| Caddy
    UptimeMonitor -->|GET /health| Caddy

    Caddy -->|Proxy /api/*, /webhooks/*, /health| Backend
    Caddy -->|Proxy /gateway/*| Gateway

    %% Backend Integrations
    Backend -->|Async DB Queries / Connection Pool| Postgres
    Backend -->|Multimodal Chat & Vision Prompt| Gemini
    Backend -->|Voice Audio URL Transcription| Deepgram

    %% Backups
    BackupJob -->|pg_dump| Postgres
    BackupJob -->|rclone sync| CloudflareR2
```

---

## Component Responsibilities

| Service | Technology | Port (Internal) | External Access | Key Responsibility |
|---|---|---|---|---|
| **Caddy** | Caddy v2 Alpine | `80`, `443` | `80`, `443` (Public) | Handles HTTPS certificates via Let's Encrypt, security headers, and routes inbound traffic. |
| **Backend** | Python 3.11 / FastAPI | `8000` | Via Caddy only | Runs Gemini multimodal AI agent, tenant-isolated DB queries, owner copilot commands, and business onboarding. |
| **Gateway** | Node.js 20 / Baileys | `3001` | Via Caddy (`/gateway/*`) | Bridges WhatsApp Web protocol, auto-downloads media (images/voice) into Base64 for the AI engine. |
| **PostgreSQL** | PostgreSQL 16 Alpine | `5432` | Internal Docker network only | Relational and catalog store for tenants, products, customers, and conversation histories. Zero port exposure on the public internet. |
