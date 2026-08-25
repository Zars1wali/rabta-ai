# RABTA AI — Full System Audit Report

**Date:** August 25, 2026
**Auditor:** Engineering Lead Review
**Purpose:** Honest assessment of what exists before rebuild decision

---

## 1. INVENTORY — Every File and What It Actually Does

### Backend Core

| File | Purpose | Status |
|------|---------|--------|
| `app/main.py` | FastAPI entry point. Serves static HTML, mounts 7 routers, initializes Qdrant on startup. | Working but fragile — Qdrant init silently fails |
| `app/core/config.py` | Pydantic settings loader from `.env`. | Working |
| `app/models/database.py` | SQLAlchemy ORM: Tenant, CatalogItem, Customer, Conversation, Message, VisualSearchLog | **Defined but completely unused** |

### Backend API Routes

| File | Purpose | Status |
|------|---------|--------|
| `webhooks.py` (442 lines) | **The core loop.** Receives WhatsApp webhooks, routes to AI, sends reply. PILOT_TENANTS in-memory dict. | **Partially working** — text works, image pipeline has bugs, Meta WhatsApp ID is placeholder |
| `gateway_bridge.py` (202 lines) | Second message entry point — Baileys QR gateway. | Working for text only. No image handling. |
| `business_onboarding.py` (197 lines) | POST /api/business/onboard. Updates PILOT_TENANTS in-memory. | Working but ephemeral — data lost on restart |
| `admin_security.py` (84 lines) | Whitelist management for Baileys gateway. | Working |
| `social_ingest.py` (270 lines) | Scrapes URL + Gemini extracts products. | **Works standalone** but results never auto-flow into catalog |
| `compliant_ingest_v2.py` (220 lines) | Second ingestion impl — v2 with draft/confirm flow. | **Duplicate** with different schemas. Neither auto-connects. |
| `visual_search_api.py` (195 lines) | Dashboard endpoints for visual search analytics. | **Dead code** — queries PostgreSQL with no tables |

### Backend Services

| File | Purpose | Status |
|------|---------|--------|
| `store_agent.py` (402 lines) | **The actual AI brain.** System prompt, Gemini call, image match, markdown stripping, chunking. | **Working** — this is what generates replies |
| `gemini_brain.py` (87 lines) | **Second LLM service.** Different prompt, different history format. | **Dead code / duplicate.** Never called. |
| `conversation_store.py` (112 lines) | In-memory dict + JSON persistence. 24h TTL, max 16 msgs. | Working. ONLY conversation state system. |
| `knowledge_base.py` (150 lines) | Qdrant vector DB client. Text + image collections. | **Cannot function** — Qdrant not running, no data inserted |
| `embedding_service.py` (83 lines) | Gemini Embedding 2 for image/text vectors. | Working code, but **no embeddings ever generated** |
| `image_preprocessor.py` (230 lines) | YOLOv8-nano detection + heuristic fallback crop. | **ultralytics not installed** — always heuristic fallback |
| `ocr_service.py` (53 lines) | Gemini Vision OCR. | Working code, called from image pipeline |
| `deepgram.py` (51 lines) | Deepgram voice-to-text. | Working code, called for audio messages |
| `whatsapp.py` (132 lines) | Meta Cloud API sender + media downloader. | Working but **PHONE_NUMBER_ID is placeholder** |
| `owner_copilot.py` (93 lines) | Slash commands (/pause, /resume, /status, /add, /help). | **Broken routing** — commands forwarded as customer messages |

### WhatsApp Gateway (Node.js)

| File | Purpose | Status |
|------|---------|--------|
| `server.js` (351 lines) | Baileys-based WhatsApp Web link. QR scanning, message forwarding. | Running port 3001, SCANNING state (not connected) |
| `approved_numbers.json` | Whitelist for Baileys gateway. | Empty approved_numbers array |
| `auth_session/` | Baileys session storage. | Empty — no session saved |

### Data Files

| File | Purpose | Status |
|------|---------|--------|
| `businesses.json` | Seed data for 4 pilot businesses. | Loaded at startup. Two entries have placeholder phone IDs. |
| `conversation_history.json` | Persisted conversation state. | Test data only (111_222 with m0-m14 placeholders) |
| `docker-compose.yml` | PostgreSQL 16, Redis 7, Qdrant. | **Docker daemon not running.** |

### Frontend (Static HTML served by FastAPI)

| File | Purpose | Status |
|------|---------|--------|
| `index.html` (27KB) | Landing/marketing page | Exists |
| `onboard.html` (45KB) | Interactive onboarding wizard | Exists |
| `dashboard.html` (34KB) | Merchant dashboard | Exists, recently updated |
| `dashboard.js` (25KB) | Dashboard logic | Exists |
| `styles.css` (31KB) | Shared stylesheet | Exists |

### Test Files

| File | Purpose | Status |
|------|---------|--------|
| `backend/test_*.py` (10 files) | Ad-hoc test scripts in root | **Messy** — mixed with source |
| `backend/tests/` (6 files) | Organized pytest suite | 8 passing (visual search tests) |

---

## 2. CORE LOOP TEST RESULTS

Ran actual system (FastAPI port 8000, Gateway port 3001) with real HTTP requests.

### Test 1: Basic Customer Message → AI Reply

```
Customer: "bhai ye Canik pistol kitne ki hai?"
Business: Haider Arms (923040124445)
Response time: 19 seconds
Reply: "Canik METE SFx ki price ke liye pe..."
```

**Result: WORKS.** Core loop functions. Message → Gemini → contextual reply about correct product.

### Test 2: Follow-Up Message (Conversation History)

```
Customer: "iska kya scene hai? deal ho jayegi kya?"
Response time: 5 seconds
Reply: Referenced arms license requirement — contextually aware
```

**Result: WORKS.** History passed to Gemini. AI remembers previous exchange.

### Test 3: Multi-Tenant Isolation

```
Customer: "kya haal hai? lawn suit hai kya?"
Business: Sapphire Studio (923169827188)
Reply: Answered about lawn suits — correct catalog
```

**Result: WORKS** (in-memory). AI uses correct business catalog context.

### Test 4: Third Message (Go-Silent Bug Test)

```
Customer: "ok bhai dikha do jo hai budget mein"
Response time: 6 seconds
Reply: Responded about gear and accessories — still in context
```

**Result: WORKS.** "Goes silent after 2-3 messages" does NOT reproduce. 16-message window + 24h TTL working.

### Test 5: Owner Commands (/status)

```
From: Owner's own number
Command: "/status"
Reply: "Ji bhai, kisi order ka status check karna..."
```

**Result: BROKEN.** /status NOT recognized as owner command. Forwarded to customer as regular text. Owner detection matches, but command handler is bypassed.

### Test 6: Business Onboarding List

```
Total businesses: 11 (expected ~8)
Items per business: 0
```

**Result: BROKEN.** JSON-seeded businesses use `item` key, not `raw_catalog`. Endpoint returns 0 items for them.

### Test 7: Visual Search Endpoints

```
Unmatched images: 0 (worked but empty)
Stats: "error" — PostgreSQL auth failure
```

**Result: BROKEN.** PostgreSQL running with different credentials. Alembic never run. No tables.

### WhatsApp Gateway

```
Status: SCANNING (no QR generated, no account connected)
```

**Result: NOT OPERATIONAL.** Gateway running but not linked to WhatsApp.

---

## 3. FEATURE-BY-FEATURE STATUS TABLE

| Feature | Status | Evidence |
|---------|--------|----------|
| WhatsApp message → AI reply (text) | ✅ Working | Tested E2E, 5-19s latency |
| Multi-business tenant routing | ✅ Working (in-memory) | Tested with 2 businesses |
| Conversation history continuity | ✅ Working | 3+ messages, context maintained |
| Owner slash commands | ❌ Broken | /status not recognized |
| Image → visual search | ⚠️ Code exists, untested | YOLO not installed, Qdrant down |
| Voice/audio → transcription | ⚠️ Code exists, untested | Deepgram key set, code clean |
| Product CRUD in dashboard | ✅ Working | Full add/edit/delete via API |
| Image/video upload for products | ❌ Not built | No file upload field — URL only |
| Social media scanning | ⚠️ Two duplicates | Neither auto-adds to catalog |
| Instagram/Facebook/TikTok import | ⚠️ Hallucination | Gemini fabricates, no real API |
| Visual product recognition | ⚠️ Pipeline coded, no infra | Full pipeline, YOLO missing, Qdrant down |
| Multi-tenant isolation (in-memory) | ✅ Working | PILOT_TENANTS + tenant_id filter |
| Multi-tenant isolation (PostgreSQL) | ❌ Not connected | Models defined, 0 tables, 0 migrations |
| Voice/call handling | ❌ Not built | Only voice note transcription |
| Multi-language (Urdu/Pashto/Hindko) | ⚠️ Prompt only | No detection, no Pashto/Hindko rules |
| "Human tone" | ✅ Working | Well-crafted prompt + markdown strip |
| Meta Cloud API WhatsApp | ❌ Not functional | Placeholder PHONE_NUMBER_ID |
| Baileys QR gateway | ⚠️ Running, not connected | Server up, no account linked |
| Merchant dashboard | ✅ Working | Full UI with CRUD |
| Onboarding wizard | ✅ Working | HTML + API exist |
| Alembic DB migrations | ❌ Never generated | versions/ empty, no tables |
| Docker infrastructure | ❌ Not running | Docker daemon off |
| Qdrant vector DB | ❌ Not running | Required for search features |
| Redis | ❌ Not running | Configured, never imported in code |

---

## 4. CONFLICTS & ARCHITECTURAL ISSUES FOUND

### Critical Issues

**1. Two Separate LLM Services That Don't Agree**

- `gemini_brain.py` — older. "You are the top salesperson." Uses `sender` key. Called by NO route.
- `store_agent.py` — production. "You are a real human employee." Uses `role` key. Markdown stripping, image injection, chunking. Called by all routes.

Impact: `gemini_brain.py` is dead code but still imported in `webhooks.py`.

**2. Two Separate Ingestion Systems That Don't Agree**

- `social_ingest.py` — scrapes URL, Gemini extracts, `IngestedProductItem` schema
- `compliant_ingest_v2.py` — v2 with draft/confirm, `DraftProductItem` schema, different fields

Impact: Neither auto-connects to catalog. Dashboard auto-sense calls hardcoded mock.

**3. PostgreSQL Models Defined, Tables Never Created**

- `database.py` defines 6 models. `alembic/versions/` is empty. PostgreSQL running with wrong credentials.

Impact: Entire data persistence layer is fiction. Everything is in-memory.

**4. WhatsApp Two Entry Points, Different Capabilities**

- `webhooks.py` — Meta Cloud API. Text + audio + images. Owner detection. Visual search.
- `gateway_bridge.py` — Baileys QR. Text ONLY. No images. No owner detection.

Impact: QR gateway (the working one) loses image recognition, owner commands, visual search.

**5. Config vs Reality Mismatch**

- `GEMINI_MODEL=gemini-3.6-flash` — model does not exist (Gemini uses 2.0-flash, 2.5-flash, etc.)
- `WHATSAPP_PHONE_NUMBER_ID=your_whatsapp_phone_number_id` — placeholder
- `WHATSAPP_ACCESS_TOKEN` appears real but useless without valid Phone Number ID
- Qdrant on localhost:6333 — not running
- Redis on localhost:6379 — not running, never imported

**6. conversation_history.json Contains Garbage**

- Only entry: `111_222` with `m0`-`m14` — test placeholders from earlier debugging

### Minor Issues

**7. Business List Returns Duplicates and Wrong Counts**

- JSON entries loaded under 3 keys each (phone_number_id, business_phone, +business_phone)
- List endpoint iterates ALL keys = 3x duplicates
- JSON-seeded businesses show 0 items (no `raw_catalog`)

**8. Fragile Variable Scoping in webhooks.py**

- `image_match_context` defined inside `elif msg_type == "image"` block
- Referenced later with `'image_match_context' in dir()`
- Works by accident, brittle

**9. ultralytics (YOLO) Not Installed**

- Image preprocessor always falls back to heuristic crop (top/bottom 15% trim)

**10. No `__init__.py` Files**

- All `app/` subdirectories missing `__init__.py`
- Works via Python 3.14 implicit namespace packages, non-standard

---

## 5. BLUNT PRIORITY VERDICT

### Verdict Per Subsystem

| Subsystem | Verdict |
|-----------|---------|
| **Store Agent (AI brain)** | ✅ **Build on this.** Strongest piece. Good prompts, edge cases handled. |
| **Conversation Store** | ✅ **Build on this.** Simple, works, persists. Replace with DB later. |
| **WhatsApp Gateway (Baileys)** | ⚠️ **Fix before anything else.** Running but not connected. ONLY way to receive messages. |
| **Meta Cloud API Webhook** | ❌ **Abandon for now.** Placeholder config. Baileys is the realistic path. |
| **PostgreSQL / SQLAlchemy** | ❌ **Throw away current state.** 6 models, 0 tables, 0 migrations. The codebase doesn't use the DB for anything. |
| **Qdrant / RAG Pipeline** | ❌ **Not functional.** Qdrant down, no embeddings generated, search_catalog never called. The RAG system is a fiction. |
| **Visual Search Pipeline** | ❌ **Impressive code, zero infrastructure.** YOLO missing, Qdrant down, no vectors, PG logs don't work. |
| **Social Ingestion (2 implementations)** | ❌ **Throw away.** Two duplicates, neither connects to catalog, one hallucinates products. |
| **Dashboard** | ✅ **Build on this.** Polished UI, CRUD works. Needs real data source. |
| **Owner Copilot** | ❌ **Broken.** Commands don't route correctly. Needs rewrite. |
| **Deepgram (Voice)** | ⚠️ **Working but untested.** Keep, test later. |

### Recommended Minimum Path Forward

**Goal:** One real test business on WhatsApp, receiving AI replies that reference their products, running 24/7 on one machine.

#### Step 1: Connect the Baileys Gateway

The gateway server is running on port 3001 but not linked to any WhatsApp account. Scan the QR code, establish a session. This is the single blocking step — nothing else matters until messages flow.

#### Step 2: Fix Owner Command Routing

`/status`, `/pause`, `/resume` commands are broken due to phone number normalization edge case. Small fix, big usability win.

#### Step 3: Fix businesses.json → PILOT_TENANTS Loading

JSON-seeded businesses load as text-only `catalog_context` with no `raw_catalog` array. Dashboard shows 0 items. Fix the loading code to populate `raw_catalog` from the JSON catalog items.

#### Step 4: Delete Dead Code

- Delete `gemini_brain.py` — dead duplicate, still imported in `webhooks.py`
- Delete or merge `compliant_ingest_v2.py` — duplicate ingestion with different schema
- Remove `visual_search_api.py` routes — queries PostgreSQL with no tables

#### Step 5: Run Real Test Conversation

Have a real business owner use the Baileys gateway. Send product photos. Observe failures. Document.

#### What to Deliberately Pause

- **PostgreSQL migration** — in-memory PILOT_TENANTS works for single-process dev. Migrate when you need persistence across restarts.
- **Qdrant / RAG / embeddings** — AI answers from `catalog_context` string in prompt. Vector search is optimization for 100+ products. Prompt injection works now.
- **Visual search / image recognition** — infrastructure requirements make this Phase 2. Get text working first.
- **Social media auto-scraping** — marketing feature, not core product.
- **Dashboard visual search tabs** — delete until pipeline produces data.

### Bottom Line

The system is roughly **40% built**. The AI brain and conversation handling are genuinely good. The infrastructure layer (database, vector search, image recognition) is a fiction — code exists but nothing is connected. The WhatsApp integration has two entry points, neither currently connected to a real WhatsApp account.

**For a single test business, the fastest path to a working demo is:**
1. Connect Baileys
2. Fix owner routing
3. Seed PILOT_TENANTS correctly
4. Test with real messages

Everything else is premature optimization.
