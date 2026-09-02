# Rabta AI — Full Architecture Map & Health Assessment (Decision-Support Audit)

**Date**: September 2, 2026  
**Document Purpose**: Decision-support assessment of the live Rabta AI architecture, conversation engine, state management, and production readiness.

---

## PART 1 — FULL SYSTEM INVENTORY & ARCHITECTURE MAP

### 1. Running Services & Deployment Status

| Service | Technology | Deployment Method | Actual Current State | Dependencies / Depended On By |
|---|---|---|---|---|
| **API Backend (`rabta_backend`)** | Python 3.11, FastAPI, Uvicorn, LangGraph, SQLAlchemy Async | Docker container (`rabta_internal` network) on Linux VPS | **Healthy / Live** | Depends on `rabta_postgres`. Depended on by `rabta_gateway` and `rabta_caddy`. |
| **WhatsApp Gateway (`rabta_gateway`)** | Node.js 20, Baileys (`@whiskeysockets/baileys`), Express | Docker container with persistent volume (`gateway_auth`) | **Healthy / Live** | Depends on `rabta_backend`. Interfaces with WhatsApp Web servers. |
| **Database (`rabta_postgres`)** | PostgreSQL 16 Alpine + `pgvector` extension | Docker container with persistent volume (`postgres_data`) | **Healthy / Live** | Core dependency for backend (checkpoints, catalog, tenants, messages). |
| **Reverse Proxy (`rabta_caddy`)** | Caddy 2 Alpine (Auto-TLS, reverse proxy) | Docker container binding ports 80 & 443 | **Healthy / Live** | Routes incoming traffic to backend and static assets (`/static/catalog_images`). |

---

### 2. External Integrations Reality Check

| Integration | Technology / Provider | Purpose | Status in Live System | Notes / Reality |
|---|---|---|---|---|
| **WhatsApp Protocol** | **Baileys Web Socket** (Node.js) | QR-linked WhatsApp session handling incoming/outgoing messages | **GENUINELY LIVE** | Primary and only active messaging channel in production right now. |
| **WhatsApp Cloud API** | Meta Graph API | Official WhatsApp Business API | **CONFIGURED BUT INACTIVE** | Webhook routers (`app/api/webhooks.py`) exist in code, but runtime routing passes through `gateway_bridge.py` via Baileys. |
| **LLM (Text & NLU)** | Google Gemini 2.0 Flash (`google-genai` SDK) | Customer conversation generation, owner intent extraction | **GENUINELY LIVE** | Active in `customer_sales_chat`, `run_owner_nlu`, and spec retrieval. |
| **LLM (Vision)** | Gemini 2.0 Flash Multimodal | Firearm identification from owner/customer photos | **GENUINELY LIVE** | Active in `handle_owner_add_product` and `customer_sales_chat`. |
| **Speech-to-Text** | Deepgram Nova-2 (`deepgram-sdk`) | WhatsApp voice note transcription | **GENUINELY LIVE** | Active in `gateway_bridge.py`; triggers automatically on audio payloads. |
| **Vector Embeddings** | Gemini Embedding Model + `pgvector` | Semantic knowledge base & catalog search | **PARTIALLY USED** | Ingest and search scripts exist; production product lookup currently relies primarily on indexed SQL queries + live catalog cache. |
| **Media / Asset Storage** | Local Disk (`/app/app/static/catalog_images`) | Storage for firearm catalog photos | **GENUINELY LIVE (LOCAL)** | Served via FastAPI static mount & Caddy; Cloudflare R2 client is configured in `config.py` but inactive in live flow. |

---

### 3. Architecture Reality Diagram

```mermaid
flowchart TD
    subgraph ClientLayer ["Messaging Layer"]
        WA[WhatsApp App - Customer / Owner]
    end

    subgraph InfraLayer ["Production VPS (Docker Compose)"]
        Caddy[Caddy Reverse Proxy :80/:443]
        Gateway[WhatsApp Baileys Gateway Node.js :3001]
        
        subgraph BackendContainer ["FastAPI Backend :8000"]
            Bridge[gateway_bridge.py]
            STT[Deepgram STT Service]
            
            subgraph LangGraphEngine ["LangGraph State Machine Engine"]
                RouteMsg[route_message Node]
                
                subgraph CustomerBranch ["Customer Graph Path"]
                    CustNLU[run_customer_nlu Node\n(Regex/Rule Heuristics)]
                    CustRouter{route_customer Edge}
                    CustChat[customer_sales_chat Node\n(Gemini 2.0 Flash + Live Catalog)]
                    CustCollect[collect_customer_info Node\n(Progressive State Trap)]
                    CustCity[ask_city / ask_city_again\n(Templated Strings)]
                    CustPatience[send_patience_reply\n(Templated String)]
                end
                
                subgraph OwnerBranch ["Owner Graph Path"]
                    OwnerNLU[run_owner_nlu Node\n(Gemini 2.0 JSON Classifier)]
                    OwnerRouter{route_owner Edge}
                    OwnerCmd[handle_owner_command Node\n(Slash Commands)]
                    OwnerAdd[handle_owner_add_product Node\n(Multi-Turn Intake + Vision)]
                    OwnerPrice[extract_and_match_price Node\n(DB Catalog Matching)]
                    OwnerConfirm[handle_confirmation Node\n(DB Commit / Cache Bust)]
                    OwnerRelay[relay_owner_answer Node\n(Escalation Resolution)]
                    OwnerGreet[handle_owner_greeting Node\n(Templated String)]
                    OwnerClarify[handle_owner_inquiry_clarification Node\n(Templated String)]
                    OwnerFallback[owner_fallback Node\n(Templated Strings)]
                end
            end
        end

        subgraph DataLayer ["Data & Storage"]
            PG[(PostgreSQL 16\n- CatalogItems\n- Checkpoints / Threads\n- PriceChangeLogs\n- Conversations / Messages)]
            LocalStorage[(Local Static Storage\n/static/catalog_images)]
            MemEsc[In-Memory Escalation Dict\n_global_escalations]
        end
    end

    subgraph ExternalAPIs ["External Cloud APIs"]
        Gemini[Google Gemini 2.0 Flash API]
        DeepgramAPI[Deepgram Nova-2 API]
    end

    WA <-->|WebSocket| Gateway
    Gateway -->|HTTP POST /api/gateway/process-message| Bridge
    Gateway <-->|Audio Stream| DeepgramAPI
    Bridge --> RouteMsg
    RouteMsg -->|is_boss=False| CustNLU
    RouteMsg -->|is_boss=True| OwnerNLU
    
    CustNLU --> CustRouter
    CustRouter --> CustChat
    CustRouter --> CustCollect
    CustRouter --> CustCity
    CustRouter --> CustPatience
    CustChat <--> Gemini
    CustChat <--> PG
    
    OwnerNLU <--> Gemini
    OwnerNLU --> OwnerRouter
    OwnerRouter --> OwnerAdd
    OwnerRouter --> OwnerPrice
    OwnerRouter --> OwnerConfirm
    OwnerRouter --> OwnerRelay
    OwnerRouter --> OwnerGreet
    OwnerRouter --> OwnerClarify
    OwnerRouter --> OwnerFallback
    OwnerRouter --> OwnerCmd
    OwnerAdd <--> Gemini
    
    LangGraphEngine <-->|Thread Checkpoint Persistence| PG
    OwnerConfirm -->|Price/Item Writes| PG
    OwnerRelay <--> MemEsc
    CustCollect --> MemEsc
    CustChat --> MemEsc
    LocalStorage <--> CustChat
    Caddy --> Gateway
    Caddy --> BackendContainer
```

---

## PART 2 — MAP THE CONVERSATION ENGINE, NODE BY NODE

### 1. Classification & Failure Risk Analysis

| Node Name | Flow Branch | Classification | Risk Level | Specific Real-World Phrasing Variation It Fails On |
|---|---|---|---|---|
| `route_message` | Entry | **(d) Pure logic / routing** | **None** | Pure boolean dispatch based on incoming sender phone number vs registered `tenant.owner_phone`. |
| `run_customer_nlu` | Customer | **(c) Hybrid / Rule-Heavy** | **Medium** | Does not call LLM. Uses regex/keyword lists for city, product, delivery, legal, and photo intent. Fails or misclassifies if a customer uses unlisted slang for delivery, typos in city names (e.g. "Rwp" instead of "Rawalpindi" or "Isb" instead of "Islamabad"), or complex multi-intent sentences. |
| `customer_sales_chat` | Customer | **(a) Genuine LLM-generated reply** | **Low** | Calls Gemini 2.0 Flash with system prompt and catalog context. Handles varied Urdu-English phrasing, colors, specs, and sales negotiation naturally. Image resolution logic intercepts photo requests deterministically before LLM hallucination occurs. |
| `collect_customer_info` | Customer | **(b) Hardcoded / templated reply** | **High** | Fixed template sequence (`name → city → address`). If customer says *"Bhai pehle charges toh batao main delivery baad mein sochunga"* (Asking for estimate before committing address), this node ignores their request and repeats the hardcoded template: *"Bhai, exact address ke baghair courier ko... deliver karna mushkil hoga"*. |
| `ask_city` | Customer | **(b) Hardcoded / templated reply** | **High** | Fixed string: *"Delivery bilkul ho sakti hai. Aap kis city mein mangwana chahte hain?"*. Fails to acknowledge context if customer said *"Main Gujranwala bypass ke paas rehta hoon, deliver ho sakta hai?"* (Repeats template asking for city even though bypass/location was hinted). |
| `ask_city_again` | Customer | **(b) Hardcoded / templated reply** | **High** | Fixed string: *"Bhai please city batayein — kis city mein delivery chahiye?"*. Repeated robotically if the customer asks a clarifying question instead of naming a city. |
| `send_patience_reply` | Customer | **(b) Hardcoded / templated reply** | **High** | Fixed string: *"Main abhi bhi shop se confirm kar raha hoon, thori si sabr karein."*. Completely ignores whatever the customer actually typed while waiting (e.g. *"Acha chalain Glock chhorain, Taurus ki price bata dain"* is ignored and met with the canned patience line). |
| `escalate_to_owner` | Customer | **(d) Pure logic / routing** | **Low** | Thin adapter routing legacy city-only escalations into `collect_customer_info`. |
| `run_owner_nlu` | Owner | **(a) Genuine LLM extraction** | **Low** | Calls Gemini 2.0 with structured JSON schema (`intent`, `product_name`, `new_price`, `relay_text`, etc.). Highly robust against varied Urdu/English phrasings, numbers with units (e.g. "450k", "4.5 lakh", "char lakh pachas hazar"). Has regex fallback. |
| `handle_owner_command` | Owner | **(b) Hardcoded / templated reply** | **Low** | Standard CLI command dispatcher (`/pause`, `/resume`, `/status`, `/prices`). Fails only if owner makes typos in commands. |
| `handle_owner_add_product` | Owner | **(c) Hybrid** | **Medium** | Parses staged fields from Gemini NLU / Vision API, but reply prompts and confirmations are templated strings. Fails if owner provides fractional or ambiguous specs in unconventional order during step-by-step intake. |
| `extract_and_match_price` | Owner | **(c) Hybrid** | **Medium** | DB query matching + templated disambiguation prompts. Fails if the owner refers to a gun by a nickname or local jargon not indexed in DB (e.g. "30 bore chota model"). |
| `handle_disambiguation` | Owner | **(b) Hardcoded / templated reply** | **Medium** | Numeric picker (1 to N) or origin string match. Fails if owner responds conversationally (e.g. *"Jo sab se mehengi wali hai"* or *"Kaali wali"* instead of typing the number "1" or "USA"). |
| `handle_confirmation` | Owner | **(b) Hardcoded / templated reply** | **Low** | Validates yes/no keywords and performs atomic DB updates. Fixed confirmation output. |
| `relay_owner_answer` | Owner | **(b) Hardcoded / templated reply** | **Medium** | Passes owner's raw answer directly to customer; replies to owner with fixed *"Done bhai. Customer ko convey kar diya."*. Fails if owner's reply was ambiguous or contained private notes intended only for the AI. |
| `handle_owner_greeting` | Owner | **(b) Hardcoded / templated reply** | **Low** | Fixed greeting: *"Jee Haider bhai, salam! Batayein koi update ya price change karni hai?"*. |
| `handle_owner_info_request` | Owner | **(c) Hybrid** | **Low** | Queries DB for catalog specs/photos using live cache; returns templated message with photo attached. |
| `handle_owner_inquiry_clarification`| Owner | **(b) Hardcoded / templated reply** | **Low** | Fixed string reminding owner what the customer asked. |
| `owner_fallback` | Owner | **(b) Hardcoded / templated reply** | **Medium** | Canned fallbacks when no intent matched. |

---

## PART 3 — END-TO-END FEATURE DATA FLOW TRACE

### 1. Customer Product Inquiry (Browse & Consultative Sales)
- **Path**: `Gateway → gateway_bridge → route_message → run_customer_nlu → route_customer → customer_sales_chat → Gateway → Customer`
- **Step Evaluation**:
  - `run_customer_nlu`: **Solid**. Accurately differentiates product queries from delivery/escalation intents.
  - `route_customer`: **Solid**. Forces color, spec, and brand questions into `customer_sales_chat`.
  - `customer_sales_chat`: **Solid**. Gemini 2.0 generates grounded, consultative responses adhering to the 23-point framework without markdown/emojis.

### 2. Image Request & Dispatch
- **Path**: `Gateway → gateway_bridge → route_message → run_customer_nlu (nlu_photo_intent=True) → route_customer → customer_sales_chat (Contextual Product Resolution + DB Query) → Gateway (Sends Media + Text) → Customer`
- **Step Evaluation**:
  - Image Resolution: **Solid**. Checks current message first against live DB catalog cache, then previous assistant turn, preventing previous-session image bleed.
  - Multi-Image Handling: **Solid**. Resolves queries like *"Dono ki pic dikhao"* into multi-item payloads.
  - Anti-Hallucination Guard: **Solid**. Regex post-filter strips phrases like *"Yeh check karein tasweer"* if no image exists in DB.

### 3. Price & Delivery Escalation to Owner
- **Path**: `Customer asks delivery/discount → run_customer_nlu → route_customer → collect_customer_info → EscalationService.create_escalation → Owner WhatsApp Alert`
- **Step Evaluation**:
  - Info Collection Trigger: **Fragile**. If customer is routed to `collect_customer_info`, they get trapped in a strict step-by-step script (Name → City → Address) that does not understand conversational side-questions.
  - Escalation Creation: **Fragile (In-Memory)**. `EscalationService` stores records in Python memory (`_global_escalations`), which is wiped on backend container restart.
  - Owner Alert Generation: **Solid**. `format_escalation_alert` builds clean, context-rich alerts without AI jargon.

### 4. Owner Natural Language Price Update
- **Path**: `Owner sends message → route_message (is_boss=True) → run_owner_nlu (Gemini JSON) → route_owner → extract_and_match_price → handle_confirmation → DB Commit + Cache Invalidation`
- **Step Evaluation**:
  - Intent & Price Extraction: **Solid**. Gemini parses "450k", "450000", "4.5 lakh" flawlessly.
  - Disambiguation: **Solid**. Generates numbered list when multiple models match (e.g. Glock 19 Gen 4 vs Gen 5).
  - Persistence & Cache Invalidation: **Solid**. Performs atomic DB commit and instantly clears `_catalog_cache` so customer chats reflect the new price immediately.

### 5. Owner Product Intake (Text & Photos)
- **Path**: `Owner sends photo/text → run_owner_nlu → handle_owner_add_product (Gemini Vision + Staging) → handle_confirmation → DB Commit`
- **Step Evaluation**:
  - Vision Identification: **Solid**. Gemini Vision identifies firearm models from uploaded images if the owner doesn't specify the model.
  - Multi-Turn Staging: **Solid**. Persists staged item state in LangGraph checkpointer across turns until confirmed.
  - Fallback / Skip Handling: **Solid**. Owner can add item in one single message or across multiple messages.

### 6. Licensing / Legal Question Handling
- **Path**: `Customer asks licensing question → run_customer_nlu (nlu_legal_intent=True) → route_customer → customer_sales_chat → Compliance Reply + High-Priority Owner Escalation Alert`
- **Step Evaluation**:
  - Keyword & Pattern Detection: **Solid**. Catches "license", "licence", "permit", "qanoon", "without license", "nadra".
  - Safe Non-Committal Response: **Solid**. Instantly issues disclaimer (*"Firearms purchase ke liye valid license aur legal requirements zaroori hain..."*) and blocks AI from speculating on legalities.
  - Escalation Alert: **Solid**. Dispatches `🚨 [LEGAL / LICENSING INQUIRY]` alert to owner.

---

## PART 4 — STATE MANAGEMENT HEALTH CHECK

### 1. Analysis of State Stores

| State Type | Where Stored | Scope / Lifecycle | Unified or Fragmented? |
|---|---|---|---|
| **Conversation Graph State** | PostgreSQL (`checkpoints` & `checkpoint_blobs` via LangGraph `AsyncPostgresSaver`) | Per thread ID: `{tenant_id}:{sender_phone}`. Persists across restarts. | **Unified Core** |
| **Escalations & Pending Inquiries** | Memory (`_global_escalations` dict in `escalation_service.py`) | Application memory. **LOST on container restart**. | **Fragmented / Fragile** |
| **Chat Message History** | PostgreSQL (`conversations` and `messages` tables via `conversation_store.py`) | Long-term message logging. Purged after 48h by background worker. | **Unified Database** |
| **Legacy Session State** | Memory (`conversation_state.py`) | Unused / Dead code. | **Orphaned (Not Active)** |

### 2. Multi-Tenant & Per-Customer Isolation Re-Verification

- **Thread ID Namespacing**: Thread IDs in LangGraph are strictly partitioned by `{tenant_id}:{sender_phone}`. A customer chatting with Business A will never touch checkpoints of Business B.
- **Turn-Level Sanitization**: Verified in `gateway_bridge.py` (lines 157–167). Turn-ephemeral fields (`media_url`, `media_urls`, `reply_chunks`, `owner_alert`, `forward_to_customer`) are explicitly wiped on every new inbound message before calling `graph.ainvoke`, eliminating the state bleed bug that previously persisted stale media URLs across turns.
- **Tenant Catalog Scoping**: All catalog queries in nodes explicitly append `.where(CatalogItem.tenant_id == t_uuid)`.

---

## PART 5 — TECHNICAL DEBT AND DUPLICATION SWEEP

### 1. Dead Code & Abandoned Modules
1. **`app/services/conversation_state.py`**: Completely abandoned. Contains old pre-LangGraph `CustomerSession` class with zero imports anywhere in the codebase. Should be deleted.
2. **`app/services/owner_copilot.py`**: Contains duplicate methods (`handle_command`, `handle_owner_natural_message`) that were used before LangGraph nodes took over. Only `format_escalation_alert` is currently in active use.
3. **`app/services/ocr_service.py` & `app/services/image_preprocessor.py`**: Tesseract / OpenCV pipeline built during initial prototyping. Currently bypassed by direct Gemini 2.0 Flash multimodal vision.

### 2. Observability & Logging Assessment
- **Current State**: **Log-Dependent / Reactive**.
- **What is logged**: Graph transitions, NLU classifications, image lookups, and latency are logged to standard output (`backend_run.log` and `gateway.log`).
- **Gap**: There is no structured tracing (e.g., OpenTelemetry / Langfuse) or alert webhooks on failures. If a customer experiences a strange reply, diagnosis still requires grepping logs or relying on user screenshots.

---

## PART 6 — HONEST OVERALL ASSESSMENT (RATING & READINESS)

### Rating Across Dimensions

| Dimension | Rating (1–10) | Reality Summary |
|---|:---:|---|
| **1. Reliability & Uptime** | **8.5 / 10** | Docker container orchestration with auto-restart, Postgres connection pooling, and healthchecks make the runtime infrastructure very stable. |
| **2. Language Flexibility** | **5.5 / 10** | **Two distinct tiers**: The sales conversation (`customer_sales_chat`) and owner intent extraction (`run_owner_nlu`) are genuine LLM and handle varied natural phrasing excellently. However, the info-collection flow (`collect_customer_info`, `ask_city`, `send_patience_reply`) is rigid and templated, making it feel robotic if the customer deviates from direct answers. |
| **3. Data Integrity & Catalog Accuracy** | **9.0 / 10** | Catalog updates from the owner atomically commit to Postgres and immediately bust the in-memory cache. Image matching verifies database existence before sending. |
| **4. Multi-Tenant Isolation** | **8.5 / 10** | Clean per-tenant DB schemas and `{tenant_id}:{sender_phone}` thread isolation. Only weakness is in-memory escalation storage. |
| **5. Production Readiness (10 Tenants)** | **6.0 / 10** | System works reliably for a single tenant (Haider Arms). Scaling to 10 tenants would hit two bottlenecks: (1) Baileys WhatsApp Web sessions (requires 10 phone QR linkings in single Node process), and (2) in-memory escalations table losing state during deploys/restarts. |

---

### What Would Break First Under Real Scale?

1. **In-Memory Escalations**: If the backend container redeploys while an owner has pending customer escalations, those escalations are wiped from memory. The owner replying later will receive *"Jee bhai note kar liya"* instead of relaying the message to the customer.
2. **WhatsApp Session Scalability**: Managing multiple concurrent retail clients over Baileys QR sessions within a single Node.js instance leads to socket disconnects and memory pressure. Transitioning to Meta Cloud API or a dedicated multi-session gateway manager will be required for multi-tenant SaaS scaling.
3. **Info Collection Trap**: When customers enter delivery escalation, the bot ceases being an intelligent sales agent and becomes a rigid form filler. If the customer asks a side question during info collection, the bot ignores it and repeats the form question.

---

## SUMMARY RECOMMENDATION FOR NEXT SPRINT

1. **Top Priority (Language Polish)**: Refactor `collect_customer_info` to let Gemini handle the collection conversationally within `customer_sales_chat` rather than routing through hardcoded templated nodes.
2. **Second Priority (Data Durability)**: Move `_global_escalations` from Python memory into a persistent `escalations` PostgreSQL table.
3. **Cleanup**: Delete dead files (`conversation_state.py`, unused functions in `owner_copilot.py`) to keep the codebase clean.
