# Rewilt Sales Ops — Metering, Depletion and Plan Changes

**Spec v1.0 — 2026-08-26** · extends `salesops-build-spec.md` (§6 schema, §11 work packages)
· prices and tiers from `salesops-token-costs-and-catalogue.md`

Covers: what counts as a billable conversation, how a tenant sees their consumption and
its trajectory, how they buy more, and how they move between tiers in both directions.

---

## 1. Principles

1. **The end customer never sees any of this.** Quota, depletion and upsell live on the
   tenant's owner surface only. The agent must never mention a limit, a plan or an upgrade
   to the tenant's customers. Put this in the agent policy refusal list.
2. **Never go dark silently.** On the other end of a depleted quota is a real shopper
   waiting for an answer. Depletion degrades the model route; it does not stop the agent.
3. **The recommendation must be honest in both directions.** If a tenant would be cheaper
   on a lower tier, say so unprompted. Same computation, same surface, no thumb on the
   scale. This costs a little revenue per month and buys the thing the whole business runs
   on, which is being believed about numbers.
4. **Downgrades take effect at period end; upgrades take effect now.** Otherwise the
   mechanism is trivially gamed by upgrading for a heavy week and dropping back.
5. **The ledger is the truth.** Counters are a cache. Any disagreement is resolved by
   recomputing from `usage_events`, never the other way.

---

## 2. What counts

### 2.1 Billable conversation

> A **billable conversation** is a 24-hour window, opened by the first inbound message
> from a given end-customer identity to a given tenant on a given channel, during which
> the agent produced at least one reply.

Consequences, all deliberate:

- One counted conversation regardless of how many turns it contains. A visitor asking
  forty questions costs us more but is not billed more; the buffer in the cost model exists
  for exactly this.
- A customer who returns the next day is a second conversation. This mirrors WhatsApp's
  own 24-hour service window, so it is explicable to any tenant who has used the Business
  Platform.
- A session where the agent never replied (bounce, budget already exhausted, blocked
  origin) is **not** billable.
- Identity: `identity_hash = HMAC-SHA256(server_secret, channel + ':' + raw_identity)`.
  Raw identity is the phone number on WhatsApp and the widget's first-party session ID on
  web. Never store the raw value in the metering tables.
- Non-billable flags: our own tenant, the tenant owner's own number, sessions marked
  `test`, and any session created by the eval harness. Set `counted = false`, keep the row.

### 2.2 What is metered but not counted against quota

- **Tokens and spend** — always recorded (`sessions.tokens_used`, `sessions.cost_minor`,
  and `spend_ledger` on Custom), used for margin analysis and for Custom billing, never for
  tier quota.
- **WhatsApp templates** — separate meter, passed through at cost + 25%. A tenant can
  deplete conversations and still have template budget, or the reverse.

---

## 3. Schema

Additive migration. Everything tenant-scoped.

```sql
-- what the tenant is entitled to for one Stripe billing period
CREATE TABLE entitlements (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  stripe_subscription_id  TEXT NOT NULL,
  period_start            TIMESTAMPTZ NOT NULL,
  period_end              TIMESTAMPTZ NOT NULL,
  tier                    TEXT NOT NULL,          -- lite|standard|europe|premium|custom
  included_conversations  INT  NOT NULL,
  block_quantity          INT  NOT NULL DEFAULT 0,
  block_size              INT  NOT NULL DEFAULT 1000,
  grace_percent           INT  NOT NULL DEFAULT 10,
  on_depletion            TEXT NOT NULL DEFAULT 'degrade',  -- degrade|autotopup|pause
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, period_start)
);

-- append-only source of truth
CREATE TABLE usage_events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  entitlement_id  UUID NOT NULL REFERENCES entitlements(id),
  session_id      UUID NOT NULL REFERENCES sessions(id),
  metric          TEXT NOT NULL DEFAULT 'conversation',
  channel         TEXT NOT NULL,
  identity_hash   TEXT NOT NULL,
  window_start    TIMESTAMPTZ NOT NULL,
  counted         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, metric, channel, identity_hash, window_start)
);
CREATE INDEX ON usage_events (tenant_id, created_at);

-- hot-path cache. never the source of truth
CREATE TABLE usage_counters (
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  entitlement_id  UUID NOT NULL REFERENCES entitlements(id) ON DELETE CASCADE,
  metric          TEXT NOT NULL,
  used            INT  NOT NULL DEFAULT 0,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, entitlement_id, metric)
);

CREATE TABLE plan_changes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL,          -- tier_up|tier_down|blocks_up|blocks_down|cancel
  from_tier       TEXT, to_tier   TEXT,
  from_blocks     INT,  to_blocks INT,
  effective       TEXT NOT NULL,          -- immediate|period_end
  effective_at    TIMESTAMPTZ NOT NULL,
  stripe_ref      TEXT,                   -- subscription or schedule id
  status          TEXT NOT NULL DEFAULT 'pending',  -- pending|applied|failed|cancelled
  requested_by    TEXT NOT NULL,          -- owner email or 'system'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE depletion_alerts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  entitlement_id  UUID NOT NULL REFERENCES entitlements(id) ON DELETE CASCADE,
  threshold       INT NOT NULL,           -- 50|80|95|100
  sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, entitlement_id, threshold)
);
```

`spend_ledger` (Custom tier prepaid balance) is defined in
`salesops-token-costs-and-catalogue.md` §5, WP-23. It is a separate concern from quota and
must not be conflated: quota is conversations, ledger is money.

---

## 4. Counting, in the request path

Inside the turn loop, immediately before the model call that will produce the first reply
of a window:

```
window_start = floor_to_hour_of_first_inbound(session, 24h window keyed by identity_hash)
INSERT INTO usage_events (...) ON CONFLICT DO NOTHING     -- idempotent by the unique key
if inserted and counted:
    UPDATE usage_counters SET used = used + 1
    evaluate depletion state → may switch route for THIS turn
```

Rules:

- The insert and the counter update are in the same transaction as the message write. A
  turn that cannot be metered does not happen. Same discipline as the spend ledger.
- `ON CONFLICT DO NOTHING` on the unique key is what makes the count exactly-once under
  concurrency. Do not attempt this with a read-then-write.
- Nightly job recomputes `usage_counters` from `usage_events`. Drift is logged as a bug,
  not silently corrected.

---

## 5. Depletion states

Let `entitled = included_conversations + block_quantity × block_size`, `grace = entitled ×
grace_percent / 100`, `used` from the counter.

| State      | Condition             | Behaviour                                                         |
| ---------- | --------------------- | ----------------------------------------------------------------- |
| `ok`       | used < 0.5 × entitled | normal                                                            |
| `notice`   | ≥ 50%                 | alert once                                                        |
| `warning`  | ≥ 80%                 | alert, show forecast and recommendation prominently               |
| `critical` | ≥ 95%                 | alert, offer one-click block purchase                             |
| `grace`    | ≥ 100%, within grace  | agent continues on the **tenant's own tier**; daily alert; banner |
| `depleted` | beyond grace          | apply `on_depletion`                                              |

`on_depletion`, per tenant:

- **`degrade`** (default) — route drops to the Lite configuration: Flash-Lite, no
  escalation, history 8, output cap 300. The agent keeps working and keeps answering
  correctly; it is simply less capable on comparisons. Tenant is told, plainly, in the
  alert. End customers are told nothing.
- **`autotopup`** — buy one block automatically via the saved payment method, up to a
  tenant-set cap of N blocks per period. Requires explicit prior consent, recorded with a
  timestamp. Every auto-purchase sends a receipt and is reversible within 24 hours.
- **`pause`** — agent stops replying and the widget shows the tenant's configured offline
  message. Only for tenants who explicitly choose it. Never the default.

A **Europe-tier tenant that degrades must degrade to a Europe-resident small model**, not
to Gemini. Data residency is the thing they bought; a cost-saving fallback that breaks it
is worse than pausing. Enforce in the route selector, and assert it in a test.

**Model route is pinned at session start.** A tenant crossing a threshold mid-conversation
finishes that conversation on the route it began with. Switching providers mid-session
changes tone, breaks caching and, on Europe, changes jurisdiction halfway through.

---

## 6. Depletion forecast

This is the feature, not the gauge. Computed server-side, shown identically to the tenant
and to us.

```
burn      = counted conversations in trailing 7 days ÷ 7
            (if period age < 7d, use period age; if < 3d, return no forecast)
remaining = entitled + grace − used
days_left = days until period_end
depletes_on   = today + (remaining ÷ burn)            -- null if burn = 0
projected_use = used + burn × days_left
```

**Recommendation** — compute all three, present the cheapest that covers `projected_use`:

1. Stay, buy blocks: `blocks_needed = ceil((projected_use − entitled) ÷ block_size)`,
   cost = `blocks_needed × block_price(tier)`, prorated for the remainder of the period.
2. Move up a tier: `base(next) + ceil((projected_use − included(next)) ÷ block_size) ×
block_price(next)`.
3. Move down a tier, offered only when `projected_use < 0.4 × included(lower)` has held for
   **three consecutive periods** — one quiet month is noise, three is a pattern.

Show the arithmetic, not just the answer: _"At 47 conversations a day you'll reach your
500 on the 22nd. Two blocks cover you to month end for €78, or Europe at €99 includes 500
and blocks are €35 — that's €169 versus €157, so blocks are cheaper this month."_ A tenant
who can check your maths trusts the next number you give them.

Never recommend Premium on volume grounds. It is a capability tier; recommending it to
someone with a simple catalog is the sleazy version of this feature and it will be
recognised as such.

---

## 7. Plan changes

### 7.1 Matrix

| Change        | Timing     | Stripe                                                                                             | Entitlement effect                                                |
| ------------- | ---------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Tier up       | immediate  | `subscriptions.update`, `proration_behavior: create_prorations`, `billing_cycle_anchor: unchanged` | New `included_conversations` applies at once; `used` carries over |
| Tier down     | period end | Subscription Schedule with a phase starting at `current_period_end`                                | Nothing changes until the boundary                                |
| Blocks up     | immediate  | update block line-item `quantity`, prorated                                                        | Entitlement increases at once                                     |
| Blocks down   | period end | scheduled quantity change                                                                          | Prevents buy-use-drop                                             |
| Cancel        | period end | `cancel_at_period_end: true`                                                                       | Service to period end, then read-only                             |
| Custom top-up | immediate  | one-time Checkout, `salesops_custom_credit`                                                        | `spend_ledger` topup row on webhook                               |

Why upgrades grant the full new allowance rather than a prorated one: it is simpler to
explain, it is what the tenant expects when they pay more mid-month, and the money
difference is small. Do not prorate allowances.

### 7.2 Guards

- Maximum **two** tier changes per billing period, `system`-initiated auto-topups excluded.
  Beyond that, the button says to contact us.
- A scheduled downgrade can be cancelled any time before the boundary. Show it as a pending
  state, not as a completed change.
- An upgrade cancels any pending downgrade.
- A downgrade that would place them below their **already-consumed** usage is allowed —
  it takes effect next period, when the counter resets. Say this explicitly in the UI, or
  support will field the question every time.
- Tier change is refused while an invoice is past due. Resolve payment first.
- Every change writes a `plan_changes` row before the Stripe call and is reconciled by the
  `customer.subscription.updated` webhook. If Stripe and our row disagree, Stripe wins and
  the mismatch is alerted.

### 7.3 Dunning

Stripe smart retries handle collection. Our side:

| Days past due | Behaviour                                                                |
| ------------- | ------------------------------------------------------------------------ |
| 0–3           | nothing visible to the tenant beyond Stripe's own email                  |
| 4–7           | banner on the owner surface, alert to owner contact                      |
| 8             | route degrades to Lite config (Europe tenants: to the EU small model)    |
| 15            | agent pauses, widget shows offline message, data retained                |
| 45            | subscription cancelled, data retained to the configured retention period |

Never delete a tenant's catalog or transcripts for non-payment inside the retention window.

---

## 8. API surface

Under `/api/salesops/account`. Owner-authenticated, tenant-scoped, never reachable from
the public widget.

| Method | Path                | Returns / does                                                                                                         |
| ------ | ------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| GET    | `/usage`            | current entitlement, `used`, state, burn, `depletes_on`, `projected_use`, recommendation, trailing 30-day daily series |
| GET    | `/usage/export`     | CSV of `usage_events` for the period. Tenants ask for this; give it to them                                            |
| POST   | `/blocks`           | `{ quantity }`. Increase immediate, decrease scheduled                                                                 |
| POST   | `/tier`             | `{ tier }`. Up immediate, down scheduled. Returns `plan_changes` row                                                   |
| DELETE | `/tier/pending`     | cancel a scheduled downgrade                                                                                           |
| POST   | `/topup`            | Custom tier only. Returns Checkout URL                                                                                 |
| GET    | `/balance`          | Custom tier only. Ledger balance, burn, projected exhaustion                                                           |
| GET    | `/portal`           | Stripe Customer Portal session URL                                                                                     |
| PUT    | `/depletion-policy` | `{ on_depletion, autoTopupCap }`. Consent timestamped                                                                  |

`GET /usage` response shape:

```ts
interface UsageResponse {
  period: { start: string; end: string; daysLeft: number };
  tier: Tier;
  entitled: number;
  used: number;
  gracePercent: number;
  state: "ok" | "notice" | "warning" | "critical" | "grace" | "depleted";
  burnPerDay: number | null;
  depletesOn: string | null;
  projectedUse: number | null;
  recommendation: {
    action: "none" | "buy_blocks" | "tier_up" | "tier_down";
    blocks?: number;
    tier?: Tier;
    costMinor: number;
    reasoning: string; // the arithmetic, in their language
  };
  series: Array<{ date: string; conversations: number }>;
  onDepletion: "degrade" | "autotopup" | "pause";
  pendingChange: PlanChange | null;
}
```

---

## 9. Owner surface

Minimum viable, in this order. Not a dashboard — a page.

1. **Gauge**: used / entitled, state colour, days left in period.
2. **Forecast line**: the sentence from §6, with the arithmetic visible.
3. **Two buttons**: buy blocks, change tier. Both open a confirmation showing the exact
   prorated charge before anything is called.
4. **Pending change banner** with a cancel link, when one exists.
5. **30-day sparkline** of daily conversations.
6. **Depletion policy selector** with plain-language consequences, not enum names.

Alerts go to the owner contact by email, and on Standard and above by WhatsApp template
(utility category — the cheap one). One alert per threshold per period, enforced by the
unique constraint on `depletion_alerts`, so a redeploy or a counter recompute cannot spam
a tenant at three in the morning.

---

## 10. Work packages

Continuing the numbering in `salesops-build-spec.md` §11. Depends on WP-12 (Stripe).

- **WP-24** Schema + repositories: `entitlements`, `usage_events`, `usage_counters`,
  `depletion_alerts`, `plan_changes`. Nightly recompute job. [02, 12]
- **WP-25** Billable-conversation counting in the turn loop, idempotent, in-transaction,
  with `identity_hash`. Concurrency test: 50 parallel turns on one identity → exactly one
  counted event. [24]
- **WP-26** Depletion state machine + route degradation, including the Europe-stays-in-EU
  rule and session-start route pinning. Tests for both. [25]
- **WP-27** Forecast and recommendation engine, pure function over ledger data, unit-tested
  against fixtures including the downgrade case. [25]
- **WP-28** `/account` API surface + Stripe subscription update and schedule handling +
  webhook reconciliation. [24, 12]
- **WP-29** Owner surface page and alerting (email, then WhatsApp templates). [27, 28]
- **WP-23** Custom-tier prepaid ledger, balance, statements. Independent of the above; ship
  when the first Custom deal is signed, not before. [12]

M1 needs none of this — a single tenant with a hard cap is fine. **WP-24 through WP-26 are
M2, before the second paying tenant.** WP-27 through WP-29 are M2.5, before the tenth.

---

## 11. Test cases that must exist

- 50 concurrent turns, one identity, one 24-hour window → exactly one counted event.
- A window that spans a period boundary is attributed to the period in which it opened.
- Tier upgrade mid-period: entitlement rises immediately, `used` is preserved, Stripe
  proration matches the confirmation the tenant was shown.
- Tier downgrade: nothing changes until `period_end`; cancelling the pending change before
  the boundary leaves the subscription untouched.
- Blocks down mid-period does not reduce entitlement until the boundary.
- Depleted Europe tenant degrades to an EU-resident model, never to a non-EU one.
- Route pinned at session start survives a threshold crossing mid-conversation.
- Depletion alert fires once per threshold per period across a redeploy and a counter
  recompute.
- The agent never mentions quota, plans or upgrades to an end customer — add to the
  adversarial suite, including when the end customer asks directly.
