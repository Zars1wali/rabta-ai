# SalesOps — Platform Architecture

**v0.1 — 2026-08-26** · companion to `SPECS.md`

The question: how hard is it to make this work for any website, given the sources?

Short answer: the agent is the easy part and is already generic. The product is four
interfaces and a library of small adapters behind them. Everything that is not one of
those four things must be shared code, or you have a consultancy with extra steps.

---

## 1. The four interfaces

Freeze these before writing M0. They cost nothing today and are expensive to retrofit once
three tenants are live.

### 1.1 `CatalogSource` — what they sell

```ts
export interface CatalogSource {
  readonly kind: string; // 'woocommerce' | 'csv' | ...
  fetch(cfg: SourceConfig): Promise<Catalog>; // full snapshot
  supportsWebhooks(): boolean; // push invalidation available?
  verify(cfg: SourceConfig): Promise<VerifyResult>; // credentials + sample rows
}
```

Every adapter normalises to the one `Catalog` type in `salesops-core/types`. The agent
never learns which adapter produced it. `verify()` is what the onboarding wizard calls so
a vendor sees five of their own products before they pay.

### 1.2 `KnowledgeSource` — everything that is not a product

This is the underrated one and the place most projects like this fail.

```ts
export interface StorePolicy {
  shipping: {
    regions: string[];
    costRule: string;
    leadTimeDays: [number, number];
  };
  returns: {
    windowDays: number;
    conditions: string;
    whoPaysReturn: "customer" | "store";
  };
  warranty: { months: number; scope: string } | null;
  payment: { methods: string[]; installments: boolean };
  hours: { timezone: string; note: string };
  contact: { humanEscalation: string };
  custom: Array<{ question: string; answer: string }>; // max 20
}
```

**Structured fields, not prose, and not retrieval.** If you hand the model a scraped
returns page it will paraphrase, and a paraphrased returns policy is a fabricated returns
policy. A fifteen-field form the vendor fills in during onboarding beats a RAG pipeline on
accuracy, cost, latency and liability, and it takes them four minutes. Page ingest is
allowed only as a _draft filler_ for that form, with the vendor confirming each field —
never as a live source. This is the same discipline as §1 of the spec: the fabrication
engine in the PoC came from letting a model fill gaps it should have left empty.

### 1.3 `CloseAction` — what "yes" means here

The reason one core serves a shoe shop, a dentist and a B2B supplier.

```ts
export type CloseAction =
  | { kind: "product_link"; urlTemplate: string }
  | { kind: "add_to_cart"; endpoint: string }
  | { kind: "capture_lead"; fields: LeadField[]; notify: NotifyTarget }
  | { kind: "book_slot"; provider: "cal" | "google"; calendarId: string }
  | { kind: "stripe_checkout"; priceMap: Record<string, string> }
  | { kind: "handoff"; target: NotifyTarget };
```

A tenant enables one or more. The funnel's `close` stage calls whichever is configured.
Our own site uses `stripe_checkout` + `capture_lead`; that is the only reason our instance
differs from a customer's.

### 1.4 `Channel` — where the conversation happens

```ts
export interface Channel {
  readonly kind: "web" | "whatsapp" | "instagram" | "email";
  receive(raw: unknown): Promise<InboundMessage>; // normalise
  send(sessionId: string, chunks: string[]): Promise<void>;
  supportsMedia: { image: boolean; audio: boolean };
}
```

The chunker and typing behaviour live behind this, not in the agent. WhatsApp gets 280-char
bursts with a 1200 ms gap; web gets one bubble with a typing indicator.

---

## 2. What is shared, always

Written once, never per tenant:

agent policy and turn loop · tool resolution and validation · funnel state machine ·
sanitizer and chunker · session, message and lead persistence · tenant resolution and
scoping · rate limits, token budgets, spend caps · Stripe billing for _our_ subscriptions ·
widget UI and embed script · admin and eval harness · LLM provider adapter.

If a tenant needs a change in any of the above, it is a `TenantConfig` field or it is a
no. Never a branch.

---

## 3. TenantConfig

One JSON document per tenant, schema-validated, versioned, editable from the admin UI.
This is the entire surface of "configurable".

```jsonc
{
  "tenantId": "uuid",
  "displayName": "Loja do Bairro",
  "locales": ["pt-PT", "en"],
  "currency": "EUR",
  "timezone": "Europe/Lisbon",

  "persona": {
    "tone": "warm_direct", // enum, not free text
    "greeting": "…", // vendor-supplied, sanitized
    "escalationPhrase": "…",
  },

  "catalog": {
    "source": "woocommerce",
    "config": { "baseUrl": "…", "keyRef": "vault://…" },
    "refresh": { "mode": "poll", "ttlMinutes": 60 },
    "staleness": { "maxAgeMinutes": 240, "onStale": "hedge_price" },
  },

  "policy": {
    /* StorePolicy above */
  },

  "closes": [
    { "kind": "product_link", "urlTemplate": "https://…/?p={sku}" },
    {
      "kind": "capture_lead",
      "fields": ["name", "email"],
      "notify": { "type": "whatsapp", "to": "…" },
    },
  ],

  "channels": [
    { "kind": "web", "allowedOrigins": ["https://lojadobairro.pt"] },
    { "kind": "whatsapp", "phoneNumberId": "…", "wabaId": "…" },
  ],

  "limits": {
    "conversationsPerMonth": 2000,
    "tokenBudgetPerSession": 40000,
    "monthlySpendCapEur": 25,
  },

  "compliance": {
    "aiDisclosure": true,
    "retentionDays": 30,
    "dpaAcceptedAt": "…",
  },
}
```

`aiDisclosure` is present but not settable to `false`. It is in the schema so it appears in
the vendor's compliance export, not so it can be turned off.

---

## 4. Adapter roadmap and effort

| Adapter                      | Effort      | Build when                                  |
| ---------------------------- | ----------- | ------------------------------------------- |
| CSV / XLSX upload            | 0.5 day     | M1. Covers literally everyone as a fallback |
| Google Sheet (published URL) | 0.5 day     | M1. Small vendors already keep stock here   |
| WooCommerce REST             | 1–2 days    | M2. The EU long tail                        |
| JSON / product-feed URL      | 1 day       | On request. Also covers custom shops        |
| Shopify                      | 2 days      | At three requests                           |
| PrestaShop / Shopware        | 2 days each | At three requests. Shopware matters in DACH |
| ERP / custom                 | quote it    | Scale tier only, priced as a project        |

| Channel            | Effort                                 |
| ------------------ | -------------------------------------- |
| Web widget         | included in M0/M1                      |
| WhatsApp Cloud API | ~1 week including WABA onboarding flow |
| Email              | 2 days                                 |
| Instagram DM       | 3 days, same Meta plumbing as WhatsApp |

| Close action                              | Effort                |
| ----------------------------------------- | --------------------- |
| `product_link`, `capture_lead`, `handoff` | 0.5 day each          |
| `stripe_checkout`                         | 1 day (already in M1) |
| `book_slot`                               | 1 day                 |
| `add_to_cart`                             | 2 days, per platform  |

**Rule: an adapter is a product, not a project.** Build one when three vendors need it.
Before that, CSV upload is the answer and it is not a bad one — vendors understand it and
it never breaks because someone changed a plugin.

---

## 5. The parts that are actually hard

Not the code. These:

**Freshness.** A stale price or stock flag makes the agent lie confidently, which is worse
than not knowing. Every catalog carries `updatedAt`; past `maxAgeMinutes` the agent hedges
("that was €49 when I last checked — the site will confirm at checkout") instead of
asserting. Webhook invalidation where the platform offers it, TTL polling where it does not.

**Per-tenant evaluation.** This is the thing that decides whether you can have 50 customers
or 8. On every catalog sync, generate a smoke set automatically from the catalog itself:
ten questions whose correct answers are derivable from the data ("what is the price of
X", "do you have Y in stock", "what is cheaper, X or Y", "do you sell Z" where Z is absent).
Run them, assert exact-match on figures, alert on failure. That is how you get confidence
that scales without your hours scaling. Build it at M2, not later.

**Onboarding without you in the room.** The bottleneck is never the code, it is whether a
vendor can go from landing page to working agent alone. Target thirty minutes: connect
source, verify five products, fill the fifteen policy fields, choose a close, preview, pay.
The €50 preview is the forcing function — if it costs you two hours of hand-holding, the
price is wrong or the wizard is.

**Tenant isolation.** Every query carries `tenant_id`. Write a test that greps the data
layer and fails on any query without it, and per-tenant encryption for source credentials
(a WooCommerce consumer key is write-capable on their shop). One leak across tenants ends
the business.

**Vertical drift.** A dentist and a hardware wholesaler need different diagnostic questions.
Resist adding vertical logic to the policy — express it as a `persona.tone` enum plus the
vendor's own custom Q&A pairs. If a vertical genuinely needs different agent behaviour,
that is a second product, and you should decline it until the first is profitable.

---

## 6. What this changes commercially

If the platform is adapters plus an eval harness, then the moat is not the agent — anyone
can write that prompt. It is the adapter library, the onboarding wizard and the evidence
that it does not lie. Price and market accordingly: "works with your WooCommerce shop in
thirty minutes" beats any claim about the model.

The packages in the economics doc still hold. Add one line: adapter availability becomes a
tier feature. CSV on Starter, platform adapters on Pro, custom source on Scale.

---

## 7. Sequencing

Do now, at M0, because it is free today and costly later:

- The four interfaces as types, even with one implementation each.
- `TenantConfig` as a schema, even with one tenant.
- Tenant ID threaded through every query from the first migration.

Do not do now:

- More than one catalog adapter. CSV plus your own JSON is enough to prove the seam.
- Vector search, a dashboard, an admin panel, a plugin, or a second channel.
- Any abstraction whose second implementation you cannot name.
