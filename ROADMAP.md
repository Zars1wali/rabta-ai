# Rewilt Sales Ops — Master Roadmap & Implementation Plan

**v1.0 — 2026-08-26** · Authoritative execution roadmap derived from `SPECS.md`, `ARCHITECTURE.md`, `Metering_and_plans_SPEC.md`, and `Salesops_token_costs_and_catalogue.md`.

---

## 1. Project Foundations & Non-Negotiables

Every task across all work packages must strictly adhere to the project core constraints:

1. **EU AI Act Article 50 Transparency**: AI disclosure label in the first message of every conversation across all locales. Non-removable, provider-enforced.
2. **Zero Hallucination / Server-Resolved Tool Facts**: The model never asserts a price, stock availability, policy, or integration detail without a server-executed tool call.
3. **No Catalog Fabrication**: Deterministic catalog ingestion only (CSV, JSON, WooCommerce REST). Never prompt an LLM to invent prices, products, or stock images.
4. **Strict Tenant Isolation**: `tenant_id` mandatory across every table and query. Enforced by automated CI AST/grep tests that fail the build if violated.
5. **Client Bundle Hygiene**: Zero API keys or secrets in the client bundle. Verified against built production artifacts.
6. **Compliant Infrastructure**: Paid Gemini 3.x / Vertex AI or Mistral EU endpoints only (no free-tier API usage in EEA/CH/UK). WhatsApp via Meta Cloud API only (no Baileys).

---

## 2. Platform Architecture & Monorepo Layout

### Monorepo Structure (`pnpm` workspaces)

```
packages/
  types/                 # Frozen contracts, zod schemas (no runtime deps beyond zod)
  core/                  # Transport-agnostic agent runtime, policy render, stage machine, tools, LLM adapter
  web/                   # Next.js server routes, session store, SSE chat endpoint, Stripe webhooks, widget UI
  adapters/
    catalog-json/        # Static/feed JSON catalog adapter (WP-03)
    catalog-csv/         # CSV / XLSX upload adapter (WP-15)
    catalog-woocommerce/ # WooCommerce REST API adapter (WP-15)
  eval/                  # Integrity, adversarial, and smoke test suites
apps/
  rewilt-site/           # Customer-facing Next.js application & widget embed
```

### Dependency Flow Enforcement

```
packages/types ← packages/core ← packages/web ← apps/rewilt-site
adapters/* depend ONLY on packages/types
packages/core NEVER imports Next.js, React, Stripe, or provider SDKs directly
```

---

## 3. Work-Package Roadmap & Task Breakdown

### Milestone 0: M0 — The Evening Build (Core Runtime & Staging Chat)
> **Goal:** Deploy a working conversational agent on staging talking about Rewilt packages, streaming replies via SSE, enforcing EU AI Act disclosure, and logging transcripts to PostgreSQL.

- [x] **WP-01: Frozen Contracts & Monorepo Scaffolding**
  - [x] Initialize `pnpm` monorepo workspace with TypeScript 5.x, Node 22/24, and Vitest.
  - [x] Create `packages/types` with Zod schemas:
    - [x] `CatalogItem`, `Catalog`, `VerifyResult`, `CatalogSource`
    - [x] `StorePolicy`, `CloseAction`, `Channel`, `InboundMessage`
    - [x] `StoreIdentityVerifier` (E-Store JWT / OAuth / Magic Link)
    - [x] `FunnelStage`, `AgentTurnInput`, `AgentTurnOutput`, `TenantConfig`
  - [x] Configure ESLint import-boundary rules enforcing strict architectural direction (`types ← core ← web ← apps`).
  - [x] *Acceptance:* `pnpm test` and `pnpm lint` pass across the workspace; types package builds cleanly.

- [x] **WP-02: PostgreSQL Database & Tenant-Scoped Repositories**
  - [x] Configure PostgreSQL 16 + Drizzle ORM schema:
    - [x] `tenants`, `catalog_snapshots`, `catalog_items`, `sessions`, `messages`, `tool_calls`, `leads`, `subscriptions`, `eval_runs`.
  - [x] Implement append-only catalog snapshots (replaces defective PoC delete-then-insert pattern).
  - [x] Seed script: create initial tenant `rewilt`, its `TenantConfig`, and seed package items.
  - [x] Write CI test asserting every query in the data layer explicitly filters by `tenant_id`.
  - [x] *Acceptance:* Migrations apply cleanly; seed runs idempotently; AST/query test fails if a query lacks `tenant_id`.

- [x] **WP-03: Catalog Engine & Static JSON Adapter**
  - [x] Build `core/catalog` engine with staleness detection (`maxAgeMinutes`, `onStale: hedge_price`).
  - [x] Build `adapters/catalog-json` implementing `CatalogSource` interface.
  - [x] Implement `verify(cfg)` returning item count, sample of 5 items, and validation warnings.
  - [x] *Acceptance:* Unit tests verify catalog snapshot loading, staleness hedging, and `verify()` sampling.

- [x] **WP-04: LLM Provider Adapter & Core Agent Turn Loop**
  - [x] Implement `core/llm` provider adapter for Gemini 3.x Flash-Lite (default) and Flash (escalation).
  - [x] Add retry logic (2 retries with exponential backoff), 20s timeout, `max_output_tokens: 400`, `temperature: 0.5`.
  - [x] Build `core/agent` turn loop:
    - [x] Input normalization → budget check → 15-message history loading.
    - [x] Dynamic policy rendering (stage, tone, locale, store policy — strictly NO catalog text).
    - [x] Model invocation with tool declarations.
  - [x] *Acceptance:* Turn loop completes 10 turns with simulated messages without hallucinating prompt context.

- [x] **WP-05: Output Sanitizer, Chunker & Web Channel**
  - [x] Implement sanitizer in `core/agent`:
    - [x] Punctuation normalization, markdown safety, whitespace collapse.
    - [x] Emoji limiter (max 1 emoji per message, not strip-all).
  - [x] Build `channels/web` formatting for single-bubble stream with typing indicators.
  - [x] *Acceptance:* Sanitizer test suite passes regex edge cases and emoji constraints.

- [ ] **WP-06: API Routes & SSE Streaming**
  - [ ] Implement Next.js App Router API routes under `/api/salesops`:
    - [ ] `POST /session`: origin-based tenant resolution (`allowedOrigins`), session creation, returns `sessionId` and opening message.
    - [ ] `POST /chat`: turn execution with SSE stream (`token`, `event`, `done` frames).
    - [ ] `GET /health`: liveness and provider ping.
  - [ ] Persist turns, tokens used, cost minor, and messages to PostgreSQL.
  - [ ] *Acceptance:* `curl` to `/chat` yields valid SSE stream with tokens and updates session state in DB.

- [ ] **WP-07: Web Widget UI & Compliance Embed**
  - [ ] Build headless React hook `useSalesOpsChat` and embeddable UI widget in `packages/web/ui`.
  - [ ] Guarantee EU AI Act Art. 50 disclosure on first message ("AI sales assistant" badge/header).
  - [ ] Build embed script with typing animation and responsive modal.
  - [ ] Automated build artifact audit checking for leaked environment variables or API keys.
  - [ ] *Acceptance:* Widget runs embedded on staging site, starts chat, shows AI badge, and stores transcripts.

---

### Milestone 1: M1 — The Close (Tools, Funnel, Abuse Controls & Stripe)
> **Goal:** Enable the agent to autonomously qualify leads, execute tool-based lookups, handle objections, and close into Stripe subscriptions or €50 previews with full CI eval suites.

- [ ] **WP-08: Server-Resolved Tools & Audit Trail**
  - [ ] Implement server-side tools in `core/agent/tools`:
    - [ ] `search_catalog(query, category, price_range)`
    - [ ] `quote(sku, quantity, billing_interval)`
    - [ ] `get_policy(topic)`
  - [ ] Zod schema validation for all tool inputs and outputs.
  - [ ] Record every tool invocation into `tool_calls` table (input, output, latency, status).
  - [ ] Cap at max 2 model roundtrips per user turn.
  - [ ] *Acceptance:* Model correctly answers pricing questions only via `quote`/`search_catalog` tool results.

- [ ] **WP-09: Funnel State Machine & Objection Handling**
  - [ ] Implement server-controlled funnel stage progression:
    - [ ] `greet` → `discover` → `qualify` → `present` → `objection` → `close` → `won`/`handoff`/`lost`.
  - [ ] Add factual objection blocks (refusal to fabricate scarcity or false urgency).
  - [ ] *Acceptance:* Agent advances through stages sequentially and refuses fake discount/urgency tactics.

- [ ] **WP-10: Abuse Layer & Session Budget Guardrails**
  - [ ] Implement session token budgets (`tokenBudgetPerSession`), IP rate limiting, and origin protection.
  - [ ] Global spend cap check (`SALESOPS_GLOBAL_SPEND_CAP_EUR`).
  - [ ] Degradation fallback when token budget is exhausted.
  - [ ] *Acceptance:* Session exceeding 40k tokens gracefully degrades without throwing unhandled errors.

- [ ] **WP-11: CI Integrity & Adversarial Eval Suites**
  - [ ] Build `packages/eval` test runner for automated CI execution:
    - [ ] **Price Integrity**: Exact numeric match assertions against catalog prices.
    - [ ] **Negative Probing**: Assert model refuses products not in the catalog.
    - [ ] **Adversarial / Jailbreak Suite**: Prompt injection, prompt leakage, out-of-scope policies, limit queries.
  - [ ] *Acceptance:* Eval suite runs in GitHub Actions CI; 100% pass required for deployment.

- [ ] **WP-12: Stripe Integration & Checkout Tools**
  - [ ] Implement `stripe_checkout` close action using Stripe Checkout Sessions.
  - [ ] Configure Stripe Product/Price catalogue mapping with lookup keys (`salesops_lite_monthly_eur`, etc.).
  - [ ] Implement `POST /api/salesops/webhooks/stripe` with signature verification:
    - [ ] Handles `checkout.session.completed`, `customer.subscription.created/updated/deleted`.
    - [ ] Updates `subscriptions` and `entitlements` tables.
  - [ ] Generate Stripe Customer Portal session URLs.
  - [ ] *Acceptance:* Live Stripe test checkout completes, triggers webhook, and provisions subscription.

- [ ] **WP-13: Lead Capture, Consent & Human Handoff**
  - [ ] Build `POST /api/salesops/lead` route with explicit GDPR consent checkbox recording.
  - [ ] Implement `capture_lead` and `handoff` close actions.
  - [ ] Outbound notification dispatcher (`NOTIFY_WEBHOOK_URL`) for newly captured leads or human escalation.
  - [ ] *Acceptance:* Submitting lead form sends webhook payload with timestamped consent to notification target.

---

### Milestone 2: M2 — Other People’s Shops & Multi-Tenancy
> **Goal:** Turn the system into a true multi-tenant SaaS. Self-service onboarding wizard, WooCommerce/CSV catalog sync, automated smoke evals, and robust metering/depletion.

- [ ] **WP-14: TenantConfig Admin Surface & Versioning**
  - [ ] Implement admin API and guarded JSON editor for `TenantConfig`.
  - [ ] Schema validation on write with version history audit log.
  - [ ] *Acceptance:* Admin can update tenant settings without server restarts; invalid schemas rejected.

- [ ] **WP-15: CSV & WooCommerce Catalog Adapters**
  - [ ] Build `adapters/catalog-csv`: parses CSV/XLSX product exports into normalized `Catalog`.
  - [ ] Build `adapters/catalog-woocommerce`: pulls products, variations, prices, and stock via WooCommerce REST API.
  - [ ] Implement `verify(cfg)` for both adapters to sample 5 live products with error diagnostics.
  - [ ] *Acceptance:* WooCommerce sandbox connects, verifies 5 items, and syncs 100+ items into snapshot.

- [ ] **WP-16: Automated Per-Tenant Catalog Smoke Suite**
  - [ ] Build catalog-driven smoke test generator in `packages/eval`:
    - [ ] Generates 10 derived Q&A test cases from newly synced catalog items.
    - [ ] Executes turns and asserts exact match on price, stock, and non-existent SKU refusals.
    - [ ] Logs results to `eval_runs` and blocks catalog activation if smoke tests fail.
  - [ ] *Acceptance:* Syncing a catalog automatically runs smoke tests and fails if price is misquoted.

- [ ] **WP-24: Metering Schema & Hot-Path Counter Engine**
  - [ ] Create Drizzle migration for metering: `entitlements`, `usage_events`, `usage_counters`, `plan_changes`, `depletion_alerts`.
  - [ ] Implement nightly reconciliation job between `usage_events` (source of truth) and `usage_counters`.
  - [ ] *Acceptance:* Schema applied; nightly reconciliation corrects simulated cache drift.

- [ ] **WP-25: Billable-Conversation Counting in Request Path**
  - [ ] Implement 24-hour service window conversation counter inside turn transaction:
    - [ ] `identity_hash = HMAC_SHA256(server_secret, channel + ':' + raw_id)`.
    - [ ] `INSERT INTO usage_events (...) ON CONFLICT DO NOTHING`.
    - [ ] Atomic counter increment when a new conversation window opens.
  - [ ] Concurrency test: 50 parallel turns from one identity in 24h produces exactly 1 counted event.
  - [ ] *Acceptance:* Concurrency test passes with 0 race conditions.

- [ ] **WP-26: Depletion State Machine & Route Degradation**
  - [ ] Implement depletion states: `ok` (<50%), `notice` (≥50%), `warning` (≥80%), `critical` (≥95%), `grace` (≥100%), `depleted`.
  - [ ] Degradation policy execution:
    - [ ] `degrade`: switches route to Lite configuration (Flash-Lite, history 8, output 300).
    - [ ] **Europe-tier rule**: must degrade to EU-resident small model (Mistral Small), NEVER non-EU endpoints.
    - [ ] Pin model route at session start so route does not change mid-conversation.
  - [ ] *Acceptance:* Unit test verifies session route pinning and EU residency guarantee under depletion.

- [ ] **WP-17: Self-Service 30-Minute Onboarding Wizard**
  - [ ] Build streamlined onboarding flow:
    1. Connect source (CSV / WooCommerce REST).
    2. Verify 5 sample products.
    3. Fill 15-field structured `StorePolicy` form.
    4. Select close action & configure persona tone.
    5. Test preview widget.
    6. Complete Stripe checkout (€50 preview or monthly subscription).
  - [ ] *Acceptance:* Unassisted test run completes onboarding in under 30 minutes.

- [ ] **WP-18: Zero-Code Second Tenant Deployment (ZPI)**
  - [ ] Provision ZPI tenant using only `TenantConfig` and catalog ingestion.
  - [ ] **Hard acceptance criterion: Zero new lines of application code.**
  - [ ] *Acceptance:* ZPI agent operates independently with distinct catalog, policies, and origins.

---

### Milestone 2.5: M2.5 — Operational Growth & Metering Surface
> **Goal:** Empower store owners with real-time usage analytics, honest upgrade/downgrade recommendations, and automated depletion alerts.

- [ ] **WP-27: Depletion Forecast & Honest Recommendation Engine**
  - [ ] Implement pure mathematical forecast function based on 7-day trailing burn rate.
  - [ ] Calculate cheapest path: Buy Blocks vs. Upgrade Tier vs. 3-period trailing Downgrade recommendation.
  - [ ] Render transparent arithmetic breakdown in user's language.
  - [ ] *Acceptance:* Test suite passes across seasonal spikes, steady burn, and low-volume downgrade cases.

- [ ] **WP-28: Account Management API & Subscription Scheduling**
  - [ ] Build `/api/salesops/account` endpoints:
    - [ ] `GET /usage`, `GET /usage/export` (CSV download).
    - [ ] `POST /blocks` (immediate prorated add, period-end reduction).
    - [ ] `POST /tier` (immediate upgrade, period-end scheduled downgrade via Stripe Schedules).
    - [ ] `DELETE /tier/pending`, `PUT /depletion-policy`.
  - [ ] *Acceptance:* Immediate tier upgrade increases entitlement instantly; downgrade waits for period end.

- [ ] **WP-29: Owner Portal Page & Multi-Channel Alerting**
  - [ ] Build minimal owner surface page:
    - [ ] Consumption gauge + days remaining.
    - [ ] Forecast line with arithmetic explanation.
    - [ ] One-click block purchase & tier switch dialogs.
    - [ ] 30-day conversation sparkline.
  - [ ] Implement threshold alerts (50%, 80%, 95%, 100%) via email and WhatsApp utility templates (deduplicated by `depletion_alerts`).
  - [ ] *Acceptance:* Crossing 80% fires exactly one email alert and renders banner on owner page.

---

### Milestone 3: M3 — WhatsApp Cloud API & Voice
> **Goal:** Expand from web widget to Meta WhatsApp Business Cloud API with voice message transcription and merchant takeover.

- [ ] **WP-19: WhatsApp Cloud API Channel**
  - [ ] Build `channels/whatsapp` handling Meta Cloud API webhooks.
  - [ ] Implement chunker with 280-character bursts and 1200ms natural typing delays.
  - [ ] Integrate WhatsApp Template messaging with metered pass-through billing (+25%).
  - [ ] *Acceptance:* Inbound WhatsApp message receives chunked replies from agent in real time.

- [ ] **WP-20: WABA Onboarding & Number Provisioning Flow**
  - [ ] Document and automate WhatsApp Business Account (WABA) connection flow.
  - [ ] Support dedicated number provisioning (avoiding app migration friction).
  - [ ] *Acceptance:* Step-by-step onboarding wizard links a new Meta phone number ID.

- [ ] **WP-21: Deepgram Voice Note Processing**
  - [ ] Integrate Deepgram `nova-3` for inbound audio note transcription.
  - [ ] Per-tenant language selection (`pt`, `es`, `en`, `ur`).
  - [ ] **Enforce Europe-tier constraint**: block voice notes on Europe tier until EU STT provider is configured.
  - [ ] *Acceptance:* Inbound voice note transcribes and passes into agent turn loop seamlessly.

- [ ] **WP-22: Owner WhatsApp Control Plane**
  - [ ] Parse merchant owner commands: `/pause`, `/resume`, `/status`, `/takeover`.
  - [ ] Strict phone number isolation between merchant owner controls and customer conversations.
  - [ ] *Acceptance:* Merchant sending `/pause` halts automated AI replies for that conversation.

---

### On-Demand / Scale Modules
> **Trigger-based work packages built only upon signed contracts or explicit volume triggers.**

- [ ] **WP-23: Custom-Tier Prepaid Model-Spend Ledger** *(Trigger: First signed Custom deal)*
  - [ ] Implement append-only `spend_ledger` table with transaction-level token cost recording.
  - [ ] Build prepaid top-up flow via Stripe checkout (`salesops_custom_credit`).
  - [ ] Monthly PDF/signed URL statement generator for token spend reconciliation.
  - [ ] *Acceptance:* Ledger reconciles within 5% of provider invoice.

- [ ] **WP-30: Mistral & Vertex AI EU Provider Adapters** *(Trigger: First Europe-tier sale)*
  - [ ] Build provider adapter for Mistral Small 3.1 & Mistral Medium with EU data residency guarantee.
  - [ ] *Acceptance:* Complete conversation runs exclusively through EU endpoints with zero US data routing.

- [ ] **WP-31: Specialized E-Commerce Adapters** *(Trigger: ≥3 requests for specific platform)*
  - [ ] Shopify REST/GraphQL catalog adapter.
  - [ ] PrestaShop / Shopware catalog adapters.
  - [ ] Generic XML/JSON product feed adapter.

---

## 4. Quality & Verification Gates

Before closing any milestone, the following gates must be green:

| Test Gate | Scope | Command / Check |
|---|---|---|
| **Import Boundary Lint** | Dependency direction (`types ← core ← web ← apps`) | `pnpm lint:boundaries` |
| **Tenant Isolation AST** | Verify `tenant_id` exists on all database queries | `pnpm test:isolation` |
| **Secret Audit** | Check production bundle outputs for leaked keys | `pnpm audit:bundle` |
| **Integrity & Negative Evals** | Accurate prices, stock checks, out-of-catalog refusals | `pnpm test:evals:integrity` |
| **Adversarial Evals** | Prompt injection, quota probing, jailbreaks | `pnpm test:evals:adversarial` |
| **Concurrency Metering** | 50 concurrent turns = 1 billable conversation | `pnpm test:metering:concurrency` |

---

## 5. Stripe Commercial Catalogue Reference

| Product | Base Fee | Included Quota | Additional Block / 1k | Setup Fee | Lookup Key |
|---|---|---|---|---|---|
| **Sales Ops Lite** | €29 / mo | 300 convs | €19 | — | `salesops_lite_monthly_eur` |
| **Sales Ops Standard** | €79 / mo | 500 convs | €39 | — | `salesops_standard_monthly_eur` |
| **Sales Ops Europe** | €99 / mo | 500 convs | €35 | €250 | `salesops_europe_monthly_eur` |
| **Sales Ops Premium** | €199 / mo | 500 convs | €149 | €500 | `salesops_premium_monthly_eur` |
| **Store Preview** | €50 (one-time) | 1 catalog | — | — | `salesops_preview_eur` |

---

## 6. E-Store Integration Blueprint (`estore` Repo)

When connecting and selling through `estore` (`@stellar` ecosystem), the integration touches these exact decoupled surfaces without breaking existing branch workflows:

### A. E-Store Storefront (`apps/storefront`)
1. **Digital Product Catalog Entry**: Add SalesOps plan products (Lite, Standard, Europe, €50 Preview) as digital subscription/service SKUs.
2. **Order Completed Webhook Dispatcher**: On order fulfillment (Stripe webhook / checkout hook), dispatch a signed payload to SalesOps:
   ```json
   {
     "orderId": "ord_123",
     "userId": "usr_456",
     "sellerId": "sel_789",
     "tenantId": "uuid-v4",
     "planTier": "standard",
     "customerEmail": "merchant@store.com",
     "timestamp": "2026-08-26T17:00:00Z"
   }
   ```
3. **Shopper Widget Embed**: Inject the lightweight `<script>` tag in the storefront root layout with optional HMAC shopper session verification.

### B. E-Store Merchant Dashboard (`apps/dashboard`)
1. **"Sales Agent" Navigation Entry**: Adds a menu item for merchants in the dashboard sidebar.
2. **SSO Launch Token Generator**: Creates an HMAC-signed JWT containing `{ userId, sellerId, tenantId, roles: ['vendor_owner'] }` to embed/open the SalesOps portal seamlessly.

### C. Isolation & Branch Safety Rules
- All `estore` additions must be isolated on a dedicated integration branch (e.g. `feature/salesops-connector`).
- Zero direct database sharing: communication happens strictly over HTTP APIs with HMAC signature verification.

