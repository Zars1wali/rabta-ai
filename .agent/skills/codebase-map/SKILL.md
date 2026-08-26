---
name: codebase-map
description: >
  Project-specific orientation: where every kind of thing lives in this
  codebase. Fill in with concrete paths, package names, and conventions
  for Rabta AI. Load at the start of every session to know where to look
  and where to put things.
---

# Codebase Map

> This codebase map is configured specifically for Rabta AI. Keep this file
> short, accurate, and current — when the structure changes, this file
> changes in the same commit.

---

## Project Identity

- **Name:** Rabta AI
- **Purpose (one sentence):** Multi-tenant, multi-channel AI employee platform for Pakistani SMEs with low-resource language voice and chat capabilities.
- **Primary stack:** Python (FastAPI 3.11+), Node.js, PostgreSQL (Neon/Docker), Qdrant Cloud, Redis, Deepgram, Gemini Flash.
- **Repository layout:** Monorepo

### Monorepo details:

- **Package manager:** pip (backend), npm (whatsapp-gateway)
- **Workspace manifest:** N/A (independent service package structures)
- **Build orchestrator:** Docker Compose
- **Versioning mode:** Unversioned, continuous deployment
- **Workspace glob(s):** `Zars_PoC/backend/`, `Zars_PoC/whatsapp-gateway/`

See `monorepo/SKILL.md` for the discipline that applies inside the workspace.

---

## Submodules

*Rabta AI does not currently use any Git submodules.*

---

## Top-Level Structure

```
rabta-ai/
├── Zars_PoC/                     ← Free Tier MVP codebase
│   ├── backend/                  ← FastAPI backend service
│   │   ├── alembic/              ← Database migrations
│   │   ├── app/                  ← Backend source code
│   │   │   ├── api/              ← API routes / endpoints
│   │   │   ├── core/             ← Configuration and core settings
│   │   │   ├── db/               ← Database connection and session
│   │   │   ├── models/           ← Database models (SQLAlchemy)
│   │   │   └── services/         ← Business logic & integrations (Gemini, Deepgram, Qdrant, WhatsApp)
│   │   ├── tests/                ← Integration and E2E tests
│   │   ├── requirements.txt      ← Python dependencies
│   │   └── test_*.py             ← Unit tests
│   ├── whatsapp-gateway/         ← Node.js WhatsApp gateway
│   │   ├── package.json          ← Node.js dependencies
│   │   └── server.js             ← Gateway entrypoint & routing
│   ├── scripts/                  ← Deployment, backups, and setup scripts
│   ├── Caddyfile                 ← Web server and SSL proxy configuration
│   └── docker-compose.yml        ← Local Docker compose services
├── .agent/skills/                ← Agent skills (active)
├── SPECS.md                      ← Detailed product specifications
├── Metering_and_plans_SPEC.md    ← Metering and plans specifications
├── Salesops_token_costs_and_cat...← Token cost calculations
└── ARCHITECTURE.md               ← Platform architecture documentation
```

---

## Where Things Live

| Kind of thing | Where it lives | Naming convention |
|---|---|---|
| Domain entities and types | `Zars_PoC/backend/app/models/` | snake_case, PascalCase classes |
| Pure business logic | `Zars_PoC/backend/app/services/` | snake_case, PascalCase classes |
| Ports (interfaces for I/O) | `Zars_PoC/backend/app/services/` | snake_case, PascalCase classes |
| Adapters (Port implementations) | `Zars_PoC/backend/app/services/` | snake_case (e.g. `whatsapp.py`) |
| HTTP / API endpoints | `Zars_PoC/backend/app/api/` & `Zars_PoC/whatsapp-gateway/server.js` | snake_case |
| Background jobs / workers | N/A | N/A |
| Database migrations | `Zars_PoC/backend/alembic/` | standard Alembic migration naming |
| Configuration | `Zars_PoC/backend/app/core/config.py` & `.env` | snake_case, UPPERCASE env |
| Shared utilities | `Zars_PoC/backend/app/core/` | snake_case |
| Frontend components | N/A | N/A |
| Frontend pages / routes | N/A | N/A |
| Frontend state / hooks | N/A | N/A |
| Unit tests | `Zars_PoC/backend/test_*.py` & `Zars_PoC/backend/tests/` | prefix `test_` |
| Integration tests | `Zars_PoC/backend/test_*_pipeline.py` & `Zars_PoC/backend/tests/test_live_integration.py` | prefix `test_` |
| End-to-end tests | `Zars_PoC/backend/tests/test_integration_e2e.py` | prefix `test_` |

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Package / module | lowercase / snake_case | `services`, `models` |
| Public function | snake_case | `verify_webhook` |
| Internal function | snake_case prefixed with `_` | `_init_client` |
| Type / class | PascalCase | `StoreAgentService` |
| Constant | UPPERCASE | `GEMINI_API_KEY` |
| File | snake_case | `owner_copilot.py` |
| Test file | Starts with `test_` | `test_chat.py` |
| Environment variable | UPPERCASE | `DATABASE_URL` |

---

## Package / Module Dependency Direction

```
Zars_PoC/backend/app/api/      ← Entrypoint; calls services & models
    ↓
Zars_PoC/backend/app/services/ ← Business logic, LLM orchestrators & integrations; reads/writes models
    ↓
Zars_PoC/backend/app/models/   ← Pure database entity definitions (SQLAlchemy)
    ↓
Zars_PoC/backend/app/core/     ← Config, utilities, security
```

---

## Build, Run, Test

```bash
# Install dependencies (Python + Node.js)
cd Zars_PoC/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cd ../whatsapp-gateway && npm install

# Run dev / local — backend
cd Zars_PoC/backend && uvicorn app.main:app --reload --port 8000

# Run dev / local — gateway
cd Zars_PoC/whatsapp-gateway && npm start

# Run with docker compose
cd Zars_PoC && docker compose up --build

# Run all backend tests
cd Zars_PoC/backend && pytest

# Run specific backend test suite
cd Zars_PoC/backend && pytest tests/test_fixes.py
```

---

## Environment

- Required environment variables are documented in `Zars_PoC/.env.example`.
- Secrets are managed securely via environment files (`.env`) and never committed.
- Local PostgreSQL and Redis run via `docker compose up -d` using `Zars_PoC/docker-compose.yml`.

---

## Key Documents to Read

1. This file (`codebase-map`)
2. `change-discipline` skill — how to code cleanly
3. `architecture` skill — design principles
4. `monorepo` skill — monorepo structure rules
5. `third-party-integrations` skill — how to integrate APIs
