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

---

## Conversational State Graph Architecture (LangGraph)

> **Mandatory Rule for All Future Conversational Features:**
> Every conversational flow (sales chat, delivery escalation, price updates, discounts, order booking) MUST be modeled as nodes and edges within the single root graph in `backend/app/graph/builder.py`.

```mermaid
flowchart TD
    Inbound(["📩 Inbound WhatsApp Message"]) --> Route["🔀 route_message<br/>(is_boss check)"]
    
    %% Customer Flow
    Route -->|is_boss = False| CustNLU["🧠 run_customer_nlu<br/>(Extract city, product, name, delivery intent)"]
    CustNLU --> CustRouter{"⚖️ route_customer"}
    
    CustRouter -->|image_base64 present| CustSales["🤖 customer_sales_chat<br/>(Visual catalog search)"]
    CustRouter -->|state = BROWSING / RESOLVED & delivery_intent & no city| AskCity["❓ ask_city<br/>('Aap kis city mein mangwana chahte hain?')"]
    CustRouter -->|state = DELIVERY_ASKED & no city| AskCityAgain["❓ ask_city_again<br/>('City ka naam batayein')"]
    CustRouter -->|state = ESCALATED| Patience["⏳ send_patience_reply<br/>('Shop se confirm kar raha hoon')"]
    CustRouter -->|city present & delivery_intent| Escalate["🚨 escalate_to_owner<br/>(Create ESC record & notify Boss)"]
    CustRouter -->|normal query| CustSales
    
    AskCity --> End(["🏁 END"])
    AskCityAgain --> End
    Patience --> End
    Escalate --> End
    CustSales --> End

    %% Owner Flow
    Route -->|is_boss = True| OwnerNLU["🧠 run_owner_nlu<br/>(Extract price, model, origin)"]
    OwnerNLU --> OwnerRouter{"⚖️ route_owner"}
    
    OwnerRouter -->|starts with '/'| OwnerCmd["⚙️ handle_owner_command"]
    OwnerRouter -->|image / info request| OwnerInfo["📸 handle_owner_info_request<br/>('Bhai abhi koi pending photo nahi hai')"]
    OwnerRouter -->|greetings| OwnerGreet["👋 handle_owner_greeting<br/>('Jee Haider bhai, salam!')"]
    OwnerRouter -->|explicit 'Ali ko bolo...' / pending ESC| RelayAns["📨 relay_owner_answer<br/>(Forward answer & reset customer to BROWSING)"]
    OwnerRouter -->|state = AWAITING_DISAMBIGUATION| Disambig["🔢 handle_disambiguation<br/>(Pick product from list)"]
    OwnerRouter -->|state = AWAITING_CONFIRMATION| Confirm["✅ handle_confirmation<br/>(Commit price update to DB & PriceChangeLog)"]
    OwnerRouter -->|nlu_is_price_update = True| MatchPrice["💰 extract_and_match_price<br/>(Find product matches in catalog)"]
    OwnerRouter -->|fallback| OwnerFallback["💬 owner_fallback<br/>('Jee bhai note kar liya.')"]
    
    OwnerCmd --> End
    OwnerInfo --> End
    OwnerGreet --> End
    RelayAns --> End
    Disambig --> End
    Confirm --> End
    MatchPrice --> End
    OwnerFallback --> End
```

### Core Architectural Separation:
1. **The LLM (Gemini) NEVER decides what happens next.** It is restricted solely to:
   - **NLU Understanding (`graph/nodes/nlu.py`)**: Extracting entities (product, city, name, price, origin) and classifying intents.
   - **Natural Reply Generation (`graph/nodes/customer.py`)**: Generating grounded Urdu/English text based on verified catalog context.
2. **Deterministic Code Controls All State Transitions:**
   - Edges in `graph/builder.py` route conversation state based on pure typed functions.
   - States (`BROWSING`, `DELIVERY_ASKED`, `ESCALATED`, `RESOLVED`, `AWAITING_DISAMBIGUATION`, `AWAITING_CONFIRMATION`) are explicit and typed in `RabtaGraphState`.
3. **Persistent Checkpointing (`graph/checkpointer.py`):**
   - Thread ID convention: `"{tenant_id}:{sender_phone}"` (e.g. `0a28e3db-49c5...:923005510670`).
   - Checkpoints persist across backend container restarts and deploys using PostgreSQL `AsyncPostgresSaver`.
   - Resolving an escalation via `relay_owner_answer` explicitly updates the customer's persisted checkpoint via `graph.aupdate_state()` so the customer naturally returns to `BROWSING`.

