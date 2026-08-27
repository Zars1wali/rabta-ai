# SalesOps — High-Assurance Conversational Commerce Platform

SalesOps is a multi-tenant, multi-channel autonomous AI sales and support engine designed for modern e-commerce stores and B2B SaaS merchants. It combines strict catalog price integrity, GDPR and EU AI Act Article 50 transparency badges, and multi-channel coverage across Web Widgets and the Meta WhatsApp Business Cloud API.

---

## 🚀 Key Features

* **🛡️ Strict Server-Resolved Tools & Zero Hallucinations**:
  - Deterministic catalog querying (`quote`, `search_catalog`, `check_stock`, `lookup_policy`).
  - Automated price hedging and out-of-catalog refusals.
  - Audit logging of all tool invocations with millisecond latency tracking.

* **🇪🇺 EU AI Act (Art. 50 & 52) & GDPR Compliance**:
  - Mandatory visible AI disclosure badge in web widget and initial conversational turn.
  - EU-resident data routing with dedicated **Europe Tier** running on Mistral AI (Paris/Frankfurt datacenters) and EU-resident Deepgram STT.
  - Explicit timestamped lead capture consent gating.

* **📱 Multi-Channel Omnichannel Support**:
  - **Web Embed Widget**: React 19 + Next.js App Router widget with SSE streaming and responsive drawer/floating modes.
  - **Meta WhatsApp Cloud API**: Webhook challenge & signature verification, 280-char burst chunker with natural typing delays, and audio note transcription via Deepgram `nova-3`.
  - **Owner WhatsApp Control Plane**: Merchant owner management via slash commands (`/pause`, `/resume`, `/status`, `/takeover`).

* **⚡ Multi-Tenancy & Dynamic Ingestion**:
  - Pluggable catalog adapters: JSON, CSV (RFC 4180 with European float/comma normalization), WooCommerce REST API v3, and Shopify Admin API.
  - Append-only catalog snapshot versioning with automated pre-activation CI smoke tests.
  - 5-step self-service 30-minute onboarding wizard.
  - Zero-code tenant deployment (e.g. ZeroPointIntel cybersecurity SaaS tenant provisioned with 0 new lines of engine code).

* **📈 Metering, Depletion & Billing**:
  - 24-hour rolling conversation service windows deduplicated with privacy-preserving SHA-256 HMAC identity hashes.
  - Self-healing nightly reconciliation job.
  - Depletion state machine (`ok`, `notice`, `warning`, `critical`, `grace`, `depleted`) with session route pinning.
  - Honest upgrade/downgrade recommendation engine (cheapest path: Top-Up Blocks vs. Tier Upgrade vs. 3-period trailing Downgrade savings breakdown).
  - Stripe subscription checkout and instant conversation top-up blocks.

---

## 🏗️ Monorepo Structure

```
salesops/
├── packages/
│   ├── types/                     # Shared Zod schemas, domain models & interfaces
│   ├── core/                      # Domain services (DB, Catalog, LLM, Agent, Metering, Billing, Reporting)
│   ├── web/                       # Next.js App Router API handlers & React UI components
│   └── eval/                      # CI eval test suites (Integrity, Negative, Adversarial, Smoke)
├── adapters/
│   ├── catalog-json/              # JSON catalog file adapter
│   ├── catalog-csv/               # CSV / Spreadsheet catalog adapter
│   ├── catalog-woocommerce/      # WooCommerce REST API v3 adapter
│   └── catalog-shopify/          # Shopify Admin REST API adapter
```

---

## 🛠️ Development & Verification

```bash
# Install dependencies
pnpm install

# Build all workspace packages
pnpm -r run build

# Run typechecking
pnpm typecheck

# Run linter
pnpm lint

# Run full test suite (177+ unit and integration tests)
pnpm test
```

---

## 📜 License

Private & Proprietary. All rights reserved.
