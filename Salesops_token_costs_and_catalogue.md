# Rewilt Sales Ops — Token Cost Model and Stripe Catalogue

**v1.0 — 2026-08-26** · supersedes the package table in `rewilt-sales-ops-economics.md` §3

That earlier table was priced off a per-tenant monthly guess. This one is built from a
per-conversation token model, which is the unit you actually sell.

**Rate caveat, read once:** the per-token figures below come from pricing aggregators and
they disagree with each other, particularly on Mistral (Large 3 quoted at both $0.50/$1.50
and $2.00/$6.00 across sources) and on which Flash generation is current. Verify every
number on the provider's own pricing page before it goes on a public price list. The
_structure_ of the model is the durable part; the decimals are not.

---

## 1. Token accounting per conversation

### 1.1 Assumptions

|                                                       | Value         | Source                                     |
| ----------------------------------------------------- | ------------- | ------------------------------------------ |
| Rendered agent policy                                 | 2,000 tok     | `salesops-agent-policy.md` §2, measured    |
| Tool declarations (7 tools)                           | 800 tok       | schema estimate                            |
| StorePolicy block                                     | 300 tok       | typed fields, §5 of build spec             |
| **Cacheable prefix**                                  | **3,100 tok** | stable per tenant                          |
| History (15-msg window, averaged over a conversation) | 480 tok       |                                            |
| Visitor message                                       | 40 tok        |                                            |
| Tool results, when called                             | 300 tok       | 5 catalog rows                             |
| Turns per conversation                                | 6             |                                            |
| Model calls per turn                                  | 1.6           | 60% of turns call a tool → second round    |
| Output per turn                                       | 156 tok       | 120 reply + 60 tool proposal on tool turns |

Design note: put `{stage}` and `{locale_hint}` at the **end** of the rendered policy. Any
variable placed inside the prefix breaks the cache and quietly triples your input bill.

### 1.2 Result

|              | Per turn | Per conversation (×6) |
| ------------ | -------- | --------------------- |
| Cached input | 4,960    | **30,000**            |
| Fresh input  | 1,012    | **6,000**             |
| Output       | 156      | **1,000**             |

### 1.3 Cost per conversation, by route

Gemini 3.1 Flash-Lite at $0.25 / $1.50 per 1M, cached reads at 10% of input:

```
cached   30,000 × $0.025/1M = $0.00075
fresh     6,000 × $0.25 /1M = $0.00150
output    1,000 × $1.50 /1M = $0.00150
                              ---------
                              $0.00375
```

Flash class at $1.50 / $7.50, cached at $0.15:

```
cached   30,000 × $0.15 /1M = $0.00450
fresh     6,000 × $1.50 /1M = $0.00900
output    1,000 × $7.50 /1M = $0.00750
                              ---------
                              $0.02100
```

| Escalation rate         | Blended cost / conversation |
| ----------------------- | --------------------------- |
| 0% (Flash-Lite only)    | $0.0038                     |
| **15% (design target)** | **$0.0064**                 |
| 30%                     | $0.0090                     |

Fifteen percent escalation nearly doubles the bill. **The escalation rule is the single
largest cost lever in the system** — larger than model choice, larger than caching. Log
every escalation with its trigger from day one so you can tune it against real traffic.

Add voice and vision:

```
voice   20% of conversations × 1.5 min × $0.0048/min  = $0.00144
image   10% × 1,500 tok × $1.50/1M                    = $0.00023
```

**All-in modelled cost: $0.0080 ≈ €0.0075 per conversation.**

### 1.4 When explicit caching actually pays

Cache storage is charged per token per hour (~$1.00/M/hr on Flash-class models). A
3,100-token prefix held continuously costs ~$2.26/month.

| Route      | Saving per conversation | Break-even                   |
| ---------- | ----------------------- | ---------------------------- |
| Flash-Lite | $0.00675                | **~335 conversations/month** |
| Flash      | $0.04050                | **~56 conversations/month**  |

Below the break-even, an explicit cache costs more than it saves. Use implicit caching or
none on Starter-tier tenants; switch to explicit above the threshold, per tenant, as a
config flag. This is not intuitive and it is worth a comment in the code.

---

## 2. Buffer

The modelled figure is a mean. Long conversations, retries, injection probing and second
tool rounds all sit in the right tail. Buffer for pricing — but the buffer **shrinks with
volume**, because a tenant doing 10,000 conversations has a stable mean while one doing
200 does not.

| Monthly conversations | Multiplier | Buffered cost / conversation |
| --------------------- | ---------- | ---------------------------- |
| ≤ 500                 | 3.0×       | €0.023                       |
| ≤ 2,000               | 2.5×       | €0.019                       |
| ≤ 5,000               | 2.0×       | €0.015                       |
| ≤ 15,000              | 1.5×       | €0.011                       |

The buffer is a pricing decision, not a cost estimate. Say so internally so nobody later
mistakes €0.023 for what a conversation costs.

---

## 3. Cost per conversation by model tier

The plan ladder is a **model** ladder, not only a volume ladder. Four routes, same token
model from §1.2, different providers and different agent configuration.

| Tier         | Route                                                   | Config                                 | Cost / conv |
| ------------ | ------------------------------------------------------- | -------------------------------------- | ----------- |
| **Lite**     | Flash-Lite only, no escalation                          | history 8, output cap 300, text only   | **€0.0033** |
| **Standard** | Flash-Lite + 15% Flash escalation                       | history 15, output 400, voice + vision | **€0.0075** |
| **Europe**   | Mistral Small 3.1 + 15% Medium escalation, EU endpoints | full config                            | **€0.0060** |
| **Premium**  | Flash-class default + 15% frontier escalation           | full config                            | **€0.0340** |

Two things fall out of this that change how you sell.

**Turning escalation off is the cheapest lever you have.** Lite is less than half of
Standard and the only differences are the escalation rule, the history window and the
output cap — all config, no code. That is a real product difference (it will be weaker on
multi-product comparisons) and an honest one to describe.

**EU residency is cheaper than the US default at this model class.** Mistral Small at
roughly $0.10/$0.30 needs no caching to land under Gemini Flash-Lite _with_ caching. So
Europe is the best-margin tier in the catalogue. Lead with it in DACH rather than treating
it as a reluctant compliance upsell.

Premium is 4.5× Standard. It must never be sold as a flat fee with a generous allowance.

_Open item:_ Deepgram is a US processor. A genuine Europe tier needs an EU speech-to-text
path (Voxtral on La Plateforme, or Whisper self-hosted on Scaleway/OVH). Until that exists,
sell Europe as text-only or disclose the STT processor explicitly. Do not quietly route EU
audio through a US vendor on a tier whose whole value is that you don't.

---

## 4. Packages

Structure: **base fee + conversation blocks.** The base carries the fixed cost and the
tier's model; blocks carry the variable. This keeps one price page across four tiers and
means a small shop that needs EU residency is not forced to buy volume it will not use.

|                               | **Lite**               | **Standard**       | **Europe**                           | **Premium**                        |
| ----------------------------- | ---------------------- | ------------------ | ------------------------------------ | ---------------------------------- |
| Positioning                   | cheapest working agent | the default        | EU residency + DPA pack              | complex catalogs, high-value sales |
| Sovereignty                   | none                   | none               | EU endpoints, EU vendor, Art. 28 DPA | negotiable                         |
| **Base / month**              | **€29**                | **€79**            | **€99**                              | **€199**                           |
| Conversations included        | 300                    | 500                | 500                                  | 500                                |
| **Additional per 1,000**      | **€19**                | **€39**            | **€35**                              | **€149**                           |
| Setup fee                     | —                      | —                  | €250                                 | €500                               |
| Channels                      | web widget             | + WhatsApp         | + WhatsApp                           | + WhatsApp, multi-number           |
| Voice / vision                | —                      | ✓                  | ✓ (see open item)                    | ✓                                  |
| Catalog source                | CSV / Sheet            | + platform adapter | + platform adapter                   | + custom source                    |
| Languages                     | 2                      | unlimited          | unlimited                            | unlimited                          |
| Templates included            | —                      | 500 utility        | 500 utility                          | 2,500 utility                      |
| Support                       | email, 3 days          | email, 2 days      | email, 1 day                         | priority + named                   |
| —                             |                        |                    |                                      |                                    |
| AI cost at base (buffered 3×) | €3.00                  | €11.25             | €9.00                                | €51.00                             |
| Infra                         | €1.00                  | €1.50              | €1.50                                | €2.00                              |
| Stripe                        | €0.89                  | €1.99              | €2.43                                | €4.63                              |
| **COGS at base**              | **€4.89**              | **€14.74**         | **€12.93**                           | **€57.63**                         |
| **Gross margin at base**      | **83%**                | **81%**            | **87%**                              | **71%**                            |
| Margin on a block             | 57%                    | 52%                | 57%                                  | 43%                                |

Worked example: a Standard tenant at 3,000 conversations pays €79 + 2.5 blocks × €39 =
**€176.50/month**, against about €58 of buffered cost. A Europe tenant at the same volume
pays €99 + €87.50 = **€186.50** against about €47.

Annual: two months free on the base fee only, not on blocks.

WhatsApp template spend is metered and passed through at cost + 25% on every tier, never
bundled. Blocks cover conversations, not Meta's template fees.

The two things this table still does not price, and you must: **support hours** (at ~80%
margin your time is the binding constraint, which is why tiers are cut on response time)
and **value** (a part-time sales assistant in Iberia is €800–1,200/month; Standard at 3,000
conversations is a fifth of that). Nobody buys a conversation. Anchor on the assistant.

---

## 5. Custom

We do not own GPUs and should not. Custom is one of two things, both on someone else's
hardware:

**5a. Self-hosted open weights on rented EU infrastructure.** Mistral Small 4, Qwen or
Llama on Scaleway (L40S ~€1.45/hr), OVHcloud (from ~€0.36/hr on older cards) or Hetzner
GEX (€889/month dedicated, German jurisdiction, DPA concluded in-account). Rented per
engagement, sized to their traffic, ideally on **their** cloud account so the invoice and
the jurisdiction are theirs. Sovereignty as a hard requirement, or fine-tuning on their
corpus. Never a cost decision — a dedicated card does not pay for itself below roughly
120,000 conversations/month (€889 ÷ €0.0075).

**5b. A specific high-quality model the customer asks for.** Claude, GPT, Mistral Large,
whatever their procurement or their use case demands, on their chosen provider and region.

### Commercials

- **Setup: €2,500–7,500.** Provider adapter, deployment or account wiring, eval suite
  against their catalog, DPA and residency documentation, onboarding.
- **Platform: from €1,500/month.** The agent, adapters, support, eval runs, updates.
- **Model spend: prepaid, passed through at cost, monitored by us.** They fund a balance
  in advance; we meter every call against it and report. **No markup on tokens.** The
  platform fee is where we earn. This removes the conversation where a customer asks what
  your margin on their inference is, and it makes the monitoring a service rather than a
  suspicion.
- 12-month minimum term. Option 5a carries an on-call expectation — price it or exclude it
  in writing, and do not agree to a latency SLA on hardware you do not control.

### What "we monitor the costs for them" means in code

This is a new work package, not a spreadsheet. Add to the build spec:

**WP-23 — Prepaid model-spend ledger.**

- `spend_ledger` table: tenant_id, direction (topup | usage), amount_minor, currency,
  provider, model, session_id, tokens_in, tokens_out, created_at. Append-only.
- Every model call writes a usage row inside the same transaction as the message write.
  A call that cannot be metered does not happen.
- Balance = sum(topups) − sum(usage). Cached, recomputed nightly against the ledger.
- Alerts at 50%, 80%, 95%, 100% of balance to tenant and to us.
- At 100%: configurable — auto-topup via saved Stripe payment method, or degrade to the
  Standard route, or pause with a clear message. Never silently overspend on their behalf.
- Monthly statement: conversations, tokens by model, spend, effective cost per
  conversation, balance movement. PDF or a signed URL. This is the deliverable they are
  paying the platform fee for.
- Reconcile the ledger against the provider's own billing monthly. A drift over 5% is a
  bug, and finding it in month one is much cheaper than finding it in month nine.

Top-ups are Stripe one-time payments against a `salesops_custom_credit` price with a
customer-set amount, fulfilled on `checkout.session.completed` into a ledger topup row.

---

## 5b. Stripe catalogue

`lookup_key` on every Price. `TenantConfig.closes[].priceMap` resolves by lookup key,
never by a hardcoded `price_...` ID.

| Product                       | Price               | Type               | `lookup_key`                    |
| ----------------------------- | ------------------- | ------------------ | ------------------------------- |
| Sales Ops Lite                | €29 / month         | recurring          | `salesops_lite_monthly_eur`     |
|                               | €290 / year         | recurring          | `salesops_lite_yearly_eur`      |
| Sales Ops Standard            | €79 / month         | recurring          | `salesops_standard_monthly_eur` |
|                               | €790 / year         | recurring          | `salesops_standard_yearly_eur`  |
| Sales Ops Europe              | €99 / month         | recurring          | `salesops_europe_monthly_eur`   |
|                               | €990 / year         | recurring          | `salesops_europe_yearly_eur`    |
| Sales Ops Premium             | €199 / month        | recurring          | `salesops_premium_monthly_eur`  |
|                               | €1,990 / year       | recurring          | `salesops_premium_yearly_eur`   |
| Conversation block — Lite     | €19 / 1,000         | recurring, qty     | `salesops_block_lite_eur`       |
| Conversation block — Standard | €39 / 1,000         | recurring, qty     | `salesops_block_standard_eur`   |
| Conversation block — Europe   | €35 / 1,000         | recurring, qty     | `salesops_block_europe_eur`     |
| Conversation block — Premium  | €149 / 1,000        | recurring, qty     | `salesops_block_premium_eur`    |
| Onboarding — Europe           | €250                | one-time           | `salesops_setup_europe_eur`     |
| Onboarding — Premium          | €500                | one-time           | `salesops_setup_premium_eur`    |
| Store Preview                 | €50                 | one-time           | `salesops_preview_eur`          |
| WhatsApp template overage     | metered, cost + 25% | metered            | `salesops_overage_template_eur` |
| Custom — setup                | quoted              | one-time, invoice  | `salesops_custom_setup`         |
| Custom — platform             | quoted              | recurring, invoice | `salesops_custom_platform`      |
| Custom — model credit         | customer-set amount | one-time           | `salesops_custom_credit`        |

Configuration notes:

- Blocks are a second recurring line item with `quantity`, adjusted on the subscription as
  the tenant grows. That is why they are recurring-with-quantity rather than metered — it
  is predictable for them and trivial for us, and metered usage billing can wait for M2.
- Setup fees ride the first subscription Checkout Session as a one-time line item; those
  land on the initial invoice only.
- Preview is a separate `mode=payment` session; credit it on conversion with a €50 coupon
  rather than a price variant — simpler to reconcile.
- Stripe Tax on, `tax_id_collection` on, for EU B2B reverse charge.
- CHF duplicates of all four tiers for Swiss tenants; Swiss card rates differ from EEA.
- Customer Portal for cancel, upgrade and payment method.
- Model tier is a `TenantConfig` field, enforced server-side at route selection. A tenant
  on Lite must not be able to reach the escalation model, and that check belongs in the
  LLM adapter, not in the prompt.

---

## 6. Validate this against reality

Every figure here is a model. `sessions.tokens_used` and `sessions.cost_minor` are already
in the schema (build spec §6) — populate them from the first turn of M0, and add
`escalated BOOLEAN` to `tool_calls` or the messages table so escalation rate is measurable
rather than assumed.

After 200 real conversations, re-derive §1.3 from logged data and update this document.
If measured cost lands within 30% of €0.0075 the model is good enough to price on. If the
escalation rate lands above 20%, tighten the escalation rule before touching prices.
