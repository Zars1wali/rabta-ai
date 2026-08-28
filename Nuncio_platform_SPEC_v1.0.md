# Nuncio — Platform Spec v1.0

**Supersedes** `rewilt-sales-ops-spec-v0.1.md` and `rewilt-sales-ops-spec-v0.2-delta.md`. Those are history; build from this.

**Name status:** Nuncio is provisional pending free register checks (TMview, Swissreg, Zefix, domain). The name lives in one config constant so a rename stays an afternoon's work. Nothing below depends on it.

**Scope:** Milestone 1 specified to build depth. M2–M4 specified only enough to ensure M1 doesn't box them out.

---

## 1. Product

A multi-tenant platform for small businesses whose customers reach them on WhatsApp. Four capability layers on one tenant, one contact graph, one billing spine.

| Layer                      | What it does                                                               | Milestone |
| -------------------------- | -------------------------------------------------------------------------- | --------- |
| L1 — Leads                 | Contacts, leads, pipeline, timeline, assignment                            | **M1**    |
| L2 — WhatsApp Lead Manager | Official WhatsApp channel, inbox, AI replies, quote capture, owner handoff | **M1**    |
| L3 — Sales AI              | Autonomous qualification, follow-up sequences, quoting                     | M2        |
| L4 — Marketing AI          | Click-to-WhatsApp ads, campaigns, audience building                        | M3        |

L3 and L4 are worthless without a lead object to act on and a channel to act through. M1 produces both.

**Launch market:** German-speaking Switzerland, product multilingual from day one (DE/FR/IT/EN).

**First vertical:** cleaning services. Rewilt already has outreach copy in the right register, a funnel in progress, and domain familiarity.

**Positioning:** "Every enquiry answered in under a minute, day or night — and every one of them lands in one place as a proper lead." Not "AI sales agent."

---

## 2. The Swiss shape of the problem

A Winterthur cleaning company gets 5–40 WhatsApp messages a day, not 300. The pain is not volume. It is that enquiries arrive at 21:00, or while the owner is on a ladder, and a quote request that waits until tomorrow went to a competitor this evening.

This determines the whole product:

|                 | Volume markets                | Switzerland                                          |
| --------------- | ----------------------------- | ---------------------------------------------------- |
| Pain            | Can't keep up                 | Can't answer while working; slow reply loses the job |
| Lead is         | A product order               | A quote or appointment request                       |
| Knowledge base  | Products with SKUs            | Services, price ranges, coverage area, availability  |
| Close           | Owner confirms and dispatches | Owner confirms appointment or sends a fixed quote    |
| Headline metric | Orders captured               | Median response time; quote requests converted       |

The data model supports both. The go-to-market tells one story.

---

## 3. M1 boundary

**In**

- Tenant accounts, roles, invitations
- WhatsApp Cloud API channel per tenant via Meta Embedded Signup
- Unified inbox: live conversations, assignment, internal notes
- Contact records with consent provenance
- Lead records, pipeline states, activity timeline
- Offerings (products _and_ services) with ingestion paths
- AI reply layer: `off` / `suggest` / `auto`, tenant-controlled
- Structured quote and appointment request capture
- Inbound voice-note transcription
- Owner notification and one-tap confirm
- Stripe payment links
- Usage and cost metering; Stripe subscription billing
- Analytics: response time, conversations, leads created, leads won
- UI in DE/FR/IT/EN; per-contact conversation language

**Out**

- Outbound message templates of any kind (see §6.4 — this deliberately removes the entire per-language template approval problem from M1)
- Broadcasts, campaigns, marketing
- Autonomous negotiation or discounting
- Payment verification from screenshots
- Instagram, Messenger, web chat
- Outbound voice
- Translation-management UI
- Calendar integration (M1.5, immediately after launch)
- A general-purpose CRM: no custom fields, no pipeline builder, no third-party CRM imports. **The leads layer in M1 is only what the WhatsApp manager needs to produce and hold a lead.** This boundary slipping is the project's largest scope risk.
- Any prohibited vertical (§10)

---

## 4. Actors and tenancy

| Actor             | Description                                                        |
| ----------------- | ------------------------------------------------------------------ |
| Platform operator | Fromtribe OÜ, registered with Meta as Tech Provider. Not a tenant. |
| Tenant            | A merchant business. One WABA, one or more phone numbers.          |
| Owner             | Tenant admin: billing, offerings, AI mode, sees everything.        |
| Agent             | Tenant staff: inbox and leads only.                                |
| Viewer            | Read-only.                                                         |
| Contact           | The end customer on WhatsApp. Never a platform user.               |

**Isolation:** shared Postgres, `tenant_id` on every row, enforced by row-level security — not by application `WHERE` clauses alone. Object storage keys tenant-prefixed. Every background job carries tenant context.

**WhatsApp assets:** one WABA per tenant via Embedded Signup. The merchant owns the WABA, phone number and business portfolio; the platform holds revocable access. Three consequences:

1. **Policy risk is contained per tenant.** One merchant's suspension doesn't take the others down.
2. **The merchant pays Meta directly** — Tech Provider customers must add their own payment method. Nuncio invoices a subscription only; message costs never touch its balance sheet. Put this in the sales copy; it removes a pricing objection.
3. **Onboarding cap:** 200 new business customers per rolling 7 days once verified. Irrelevant for two years.

---

## 5. Domain model

Load-bearing fields only.

**tenant** — id, name, legal_name, country, vertical_pack_id, timezone, default_language, status, plan, created_at

**user** / **membership** — identity, then (tenant_id, user_id, role). One person can hold several tenants; needed for resellers later.

**channel** — id, tenant_id, type (`whatsapp`), waba_id, phone_number_id, display_number, quality_rating, messaging_limit, status, token_ref

**contact** — id, tenant_id, wa_id, display_name, name_confirmed, phone_e164, **language**, tags[], **consent_source**, **consent_at**, first_seen_at, last_seen_at, blocked

**conversation** — id, tenant_id, channel_id, contact_id, status (`open`/`snoozed`/`closed`), assignee_user_id, ai_mode, **service_window_expires_at**, last_inbound_at, last_outbound_at

**message** — id, tenant_id, conversation_id, direction, **wamid** (unique — idempotency key), type, body, detected_language, media_ref, status (`queued`/`sent`/`delivered`/`read`/`failed`), error_code, **billing_category**, **cost_estimate**, author (`contact`/`user:id`/`ai`), created_at

**lead** — id, tenant_id, contact_id, **lead_type** (`quote_request`/`appointment_request`/`product_enquiry`), source, state (§7), summary, offering_ids[], **requested_at**, score, value_estimate, currency, owner_user_id, next_action_at, created_at, closed_at, close_reason

**offering** — id, tenant_id, sku, name, description, **source_language**, translations (jsonb), **price_type** (`fixed`/`from`/`hourly`/`on_request`), price, currency, **duration_minutes**, **service_area**, in_stock, stock_qty, media_refs[], attributes (jsonb), aliases[], embedding, active

**quote_request** — id, tenant_id, lead_id, **fields** (jsonb, shape defined by the vertical pack), completeness (0–1), missing_fields[], created_at

**order** — id, tenant_id, lead_id, contact_id, line_items (jsonb), subtotal, delivery_method, delivery_address, status (§7), confirmed_by_user_id, confirmed_at

**payment** — id, tenant_id, order_id, method (`stripe_link`/`claim`), stripe_payment_intent_id, amount, status (§11), confirmed_by_user_id

**vertical_pack** — id, name, intent_set (jsonb), quote_fields (jsonb), default_tone, escalation_rules (jsonb), onboarding_checklist (jsonb), sample_offerings (jsonb)

**event** — append-only timeline: tenant_id, subject_type, subject_id, actor, type, payload, created_at. Drives the lead timeline and the audit log.

**ai_run** — tenant_id, conversation_id, purpose, model, prompt_ref, input_tokens, output_tokens, latency_ms, outcome, escalated_reason. Every AI action logged, without exception.

**Contact vs. lead** is what makes this a leads platform rather than an inbox. A contact is a person; a lead is one opportunity attached to that person. The same customer requesting a deep clean in March and a window clean in August is one contact and two leads. Getting this wrong breaks every pipeline metric downstream.

---

## 6. WhatsApp channel

### 6.1 Ingress

Dedicated webhook service, separate deployable from the app. Verify Meta signature → enqueue raw payload → return 200 immediately. Processing is asynchronous and idempotent on `wamid`. Meta retries; a duplicate delivery must never produce a duplicate message row or a duplicate AI reply.

### 6.2 Service window

Every conversation carries `service_window_expires_at` = last inbound + 24h. Inside it, free-form replies. Outside it, nothing sends in M1 (no templates). The send API refuses rather than trusting the caller. When the window closes with an open lead, the owner is notified to follow up personally.

### 6.3 Consent

`consent_source` and `consent_at` are required on contact, populated automatically when the contact messages first. M1 sends nothing proactive, so this is provenance for later rather than a gate today — but the fields exist from day one because backfilling consent is impossible.

### 6.4 Templates — deliberately deferred

Meta approves templates per language, separately, each with its own approval state. By shipping no outbound templates in M1, that entire subsystem leaves scope. The constraint re-enters the moment any template ships: the registry is keyed on (name, language), the send layer resolves from `contact.language` with a fallback chain, and refuses when no approved variant exists. Recorded now so it isn't rediscovered later.

### 6.5 Media

Inbound images, audio and documents downloaded within Meta's media TTL, stored in EU object storage under tenant-prefixed keys, served by signed URL. Outbound images from offering media. Inbound audio transcribed and stored as both audio and text.

### 6.6 Health

Subscribe per tenant to quality-rating and messaging-limit webhooks. A drop alerts the owner, throttles automated sends, and surfaces on the dashboard. A merchant whose number gets restricted will blame the platform, so make the signal visible before it becomes a ban.

---

## 7. Lead lifecycle

```
new → qualifying → interested → quoted → order_pending → won
                                            ↓
                                     lost | dormant
```

| State         | Entered when                                          | Who                                   |
| ------------- | ----------------------------------------------------- | ------------------------------------- |
| new           | First inbound from an unknown contact                 | System                                |
| qualifying    | Intent classified as enquiry                          | AI                                    |
| interested    | Offering resolved, or quote fields being collected    | AI                                    |
| quoted        | Price or price range stated to the customer           | AI (from offering data only) or human |
| order_pending | Customer confirms intent to proceed                   | AI, notifies owner                    |
| won           | Owner confirms                                        | **Human only**                        |
| lost          | Explicit decline, or owner marks                      | Either                                |
| dormant       | No reply for N days (default 14, tenant-configurable) | System                                |

Order status runs parallel: `draft → awaiting_payment → paid → confirmed → scheduled → completed | cancelled`.

**Rule:** any transition touching money or commitment requires a human. The AI proposes; the owner disposes.

---

## 8. Language

Four separate problems. Three are in M1; one is deferred with §6.4.

**8.1 Product UI.** DE, FR, IT, EN. `next-intl` or equivalent, ICU MessageFormat, locale files in version control, **no hardcoded strings from commit one** — retrofitting is the expensive path. Resolution: user preference → tenant default → browser → DE. Swiss number formatting (`1'234.50`), CHF, local date formats via `Intl`.

**8.2 Conversation language.** Not a UI concern and not servable by a translation layer: a French-speaking customer messaging a Zurich cleaner must get French back. Cost is one field plus a prompt variable — the model does the rest.

- Detect on first inbound, store on `contact.language`, **sticky** unless the contact switches for two consecutive messages.
- The AI replies in the contact's language, not the tenant's.
- Escalation summaries render in the **agent's** UI language. The owner shouldn't have to read Italian to triage an Italian thread.

**8.3 Offering content.** One source language per offering; the AI works from the source and answers in the contact's language. No translation-management UI in M1. `translations` jsonb exists for later.

**8.4 Swiss German.** Spoken by most of the target market, written informally in chat, handled materially worse than Hochdeutsch by every ASR.

- **Inbound:** transcribe, normalise to Hochdeutsch before intent classification, and **lower the escalation threshold** when dialect is detected.
- **Outbound: always Hochdeutsch.** Written Hochdeutsch is the norm for Swiss business correspondence. An AI attempting dialect gets the spelling wrong — there is no correct spelling — and reads as a gimmick.
- Collect real dialect voice notes and text during the pilot; measure intent accuracy separately from Hochdeutsch.

---

## 9. AI layer

### 9.1 Modes

`off` (inbox only, extraction still runs) / `suggest` (AI drafts, agent sends with one tap) / `auto` (AI sends unattended, whitelisted intents only).

**The tenant chooses, including auto on day one.** The choice is logged. Auto is gated only on **offering completeness** — at least 10 active offerings with prices set — which is objective and defensible, and stops a merchant switching auto on over an empty catalog and blaming the product. Edit-rate statistics appear in the dashboard as advice, never as a lock.

### 9.2 Non-overridable guardrails

Regardless of mode or tenant preference:

1. Never state a price, availability or lead time not present in the offering data. If it isn't there, escalate.
2. Escalate on: complaint, refund, discount or negotiation, payment question, unrecognised intent, low offering-resolution confidence, explicit request for a human, two failed resolution attempts.
3. Disclose that it's an automated assistant when asked, and always offer a route to the owner.
4. Every escalation posts a short summary for whoever picks the thread up.
5. Only a human moves a lead to `won`.

### 9.3 Extraction (all modes)

Language detection, intent classification, offering resolution (embedding + alias match), quote-field extraction, lead scoring, conversation summary on handoff.

### 9.4 Reply construction

One message per reply wherever possible. From 1 October 2026 each outbound message is billed separately (§12), so message-splitting has a direct cost. Enforce with a send-layer guard.

---

## 10. Onboarding and offering ingestion

The model isn't where onboarding dies; the offering data is. A merchant must reach "the assistant can answer questions about my business" **in under 20 minutes**.

Paths, in priority order:

1. **Guided setup from the vertical pack.** The cleaning pack ships with a service list, typical price structures and quote fields. The owner edits rather than creates. Fastest path for a service business and the primary one for M1.
2. **CSV / XLSX upload** with column mapper and preview.
3. **Existing WhatsApp Business catalog sync** via Graph API, for merchants who have one.
4. **WooCommerce connector.** Capability already in-house from From Tribe.
5. **Photo drop.** Merchant forwards photos with captions into a setup thread; AI drafts entries; owner approves in a review queue. Slow, but converts merchants with no structured data — which is most of them.
6. **Manual entry.**

**Activation metric:** share of tenants with ≥10 active offerings within 24h of signup. Track from launch; it is the leading indicator of everything else.

---

## 11. Quotes, orders and payment

**Quote request capture** is the core M1 capability for Swiss trades. The AI collects the fields the vertical needs — for cleaning: property type, rooms or m², frequency, location, access, preferred timing — and hands the owner a complete request rather than a transcript. `completeness` and `missing_fields` are exposed so the owner can see what's still open. Cheaper to build than order capture and worth more here.

**Appointment requests** carry `requested_at`. In M1 the owner confirms manually; M1.5 adds calendar integration, because "when can you come?" is the second question in nearly every thread.

**Orders** (product tenants) capture line items, quantity, agreed price, delivery method and address, and notify the owner with a one-tap confirm.

**Payment, Switzerland:** the platform generates a Stripe payment link and marks the order paid on the Stripe webhook. Genuinely verified.

**Payment claims** (markets without card rails) are out of M1 scope. When they arrive: a customer-submitted transfer screenshot is an **assertion**, status `claimed`, confirmed by the owner against his own bank before dispatch. No UI string, marketing claim or API field may ever describe an OCR'd screenshot as verified payment. Screenshots are trivially forged and a platform that says "verified" owns the loss. Permanent constraint.

---

## 12. Unit economics — the October 2026 change

Meta's pricing documentation confirms updates launching **1 August and 1 October 2026**.

From **1 October 2026**:

- **Service messages become billable.** Free-form replies inside the 24-hour customer-initiated window — exactly what this product sends — are charged at the same per-message rate as utility templates for the recipient's country.
- In-window utility templates lose their free status too.
- Replies from a third-party AI count as service messages. Not avoidable by architecture.

Already live from **1 August 2026**: Meta's own Meta Business Agent is billed by token at $2.00/M tokens, roughly 4–5 cents per reply. Only applies to businesses using Meta's own AI — see §13.

Exact per-country rates publish by **1 September 2026**. Switzerland sits in the **"Rest of Western Europe"** band (+41), with Austria, Belgium, Denmark, Finland, Ireland, Norway, Portugal and Sweden.

**Consequences, all binding on M1:**

1. **No flat "unlimited replies" plan.** Metered, or a bundle with a fair-use ceiling and clear overage.
2. **`cost_estimate` per message is launch-blocking**, as is a per-tenant month-to-date cost view. The merchant pays Meta directly and will ask why the bill moved.
3. **Concision is an economic feature** (§9.4).
4. **The free entry-point window gains value.** Conversations opened from a Click-to-WhatsApp ad still carry a free 72-hour window — a direct argument for pulling L4 forward.
5. Pull real Rest-of-Western-Europe rates after 1 September before quoting anyone.

---

## 13. Competitive position

Meta shipped its own AI agent for WhatsApp sales and support in mid-2026, inside the platform, no third party required. Assume every merchant has heard of it by the time you pitch.

Defensibility is therefore not "AI answers your WhatsApp". It is:

- grounded answers from the merchant's own offerings, with a hard no-invention rule
- the lead pipeline and owner workflow around the conversation
- quote capture structured for the trade
- Swiss/EU data handling and a real processor DPA
- Swiss German handling
- one place where marketing, sales and lead management eventually meet

---

## 14. Compliance

**Commerce Policy is a signup gate, not a policy page.** Prohibited: weapons, firearm parts, ammunition and explosives; alcohol; tobacco and vaping; drugs and most supplements; gambling; adult services; live animals; real and virtual currency. `vertical` is required at signup, checked against a blocklist, with an attestation. Onboarding a prohibited merchant risks their WABA _and_ Nuncio's Tech Provider standing.

**GDPR / revDSG.** The merchant is controller; Nuncio is processor. Needed before the first paying customer: a processor DPA template, a published subprocessor list (Meta, model provider, transcription provider, hosting), a retention policy (default 24 months, tenant-configurable), and contact deletion cascading through messages and media. WhatsApp message content is personal data and often special-category by accident; treat the message store accordingly.

**EU AI Act transparency:** disclose the automated system. Guardrail 3 covers it in-thread; also put it in the tenant's WhatsApp business profile.

**Separation:** any non-EU deployment (different brand, unofficial transport, different vertical history) shares no infrastructure, no WABA, no Tech Provider app, and appears in no Swiss-facing collateral, demo or case study.

---

## 15. Architecture

- **Runtime:** Node + TypeScript.
- **Data:** Postgres with row-level security; pgvector for offering embeddings.
- **Queue:** Redis + BullMQ. Separate queues for webhook ingest, AI inference, outbound send (per-number paced), media download.
- **Services:** `webhook-ingress` (thin, fast, independently scalable), `worker`, `app` (Next.js — inbox and dashboard).
- **Model layer:** behind a provider interface, swappable, every call logged to `ai_run`.
- **Transcription:** behind an interface (Whisper or Deepgram), with dialect normalisation as a distinct step.
- **Storage:** S3-compatible, EU region.
- **Hosting:** single EU region (Frankfurt or Zurich).

**Invariants:** idempotent webhook processing; per-tenant AI rate limits; outbound sends queued and paced per number; complete audit log; no cross-tenant query path that isn't RLS-protected.

**On the existing PoC:** reference implementation for conversation flow and prompt design, not a base. Single-tenant, unofficial transport, different assumptions throughout. Reading it costs less than porting it.

---

## 16. Acceptance criteria

1. A merchant completes Embedded Signup from the dashboard and has a live WhatsApp number in under 15 minutes.
2. Inbound messages appear in the inbox in under 3 seconds, p95.
3. Duplicate webhook delivery produces no duplicate message and no duplicate reply.
4. Any send outside the 24-hour window is refused by the API, not by convention.
5. In suggest mode a draft is available within 5 seconds of an inbound question.
6. In auto mode an out-of-data price question escalates rather than answering.
7. A quote request creates a lead, collects the vertical's fields, and appears on the pipeline board with a completeness score.
8. The owner is notified on WhatsApp with a one-tap confirm, and only a human can move a lead to `won`.
9. A voice note in the tenant's default language is transcribed and answered.
10. A Swiss German voice note is transcribed, normalised, and either answered correctly or escalated — never answered wrongly with high confidence.
11. Tenant A cannot read any row of Tenant B, verified by an automated test in CI.
12. A contact writing in French gets French replies while the tenant's UI stays German.
13. The UI renders in DE/FR/IT/EN with no untranslated strings, verified by a CI check for missing keys.
14. Every outbound message records a billing category and cost estimate.
15. Each tenant's dashboard shows month-to-date Meta message cost by category.
16. Auto mode cannot be enabled below 10 priced active offerings.
17. Deleting a contact removes messages and media within the deletion SLA.

---

## 17. Phase 0 — Meta Tech Provider

Calendar time, not build time. Starts now, runs parallel to everything.

1. Confirm **Fromtribe OÜ** as the verifying entity — it has the commercial-register extract, business bank account and domain that Meta wants, which an unregistered sole proprietorship does not. Confirm with the accountant, and note the product line then sits in an entity with a co-founder.
2. Create the Meta Business Portfolio; complete **Business Verification** (register extract, proof of address, verified domain).
3. Create the Meta app, add the WhatsApp product, register as **Tech Provider**, accept the terms.
4. Submit **App Review** for `whatsapp_business_management` and `whatsapp_business_messaging`; obtain Advanced Access.
5. Complete Access Verification to lift the onboarding cap to 200 customers per rolling 7 days.
6. Implement Embedded Signup against the sandbox test account before touching a real merchant.
7. Publish privacy policy, terms and the processor DPA on the verified domain. App Review will look.

Nothing reaches a real merchant until this clears. It is free.

---

## 18. Sequencing

| Phase | Content                                                             |
| ----- | ------------------------------------------------------------------- |
| 0     | Meta verification and Tech Provider approval (parallel throughout)  |
| 1     | Tenancy, auth, RLS, schema, event log, i18n scaffolding             |
| 2     | Webhook ingress, message pipeline, inbox UI, window enforcement     |
| 3     | Offerings, vertical pack (cleaning), ingestion paths 1, 2, 6        |
| 4     | AI layer in suggest mode, extraction, escalation, language handling |
| 5     | Leads pipeline, timeline, assignment, quote-request capture         |
| 6     | Owner confirm flow, Stripe payment links                            |
| 7     | Metering, subscription billing, analytics                           |
| 8     | Auto mode behind the completeness gate; pilot merchants             |
| M1.5  | Calendar integration                                                |

---

## 19. Open items

1. **Plan pricing.** Blocked on Meta's rates publishing 1 September.
2. **Name.** Free register checks outstanding: TMview, Swissreg, Zefix, domain.
3. **Transcription provider** for Swiss German — needs a bake-off against real pilot audio; no vendor's marketing claims should be trusted here.
4. **Go-to-market language.** The system is DE/FR/IT/EN; whether sales starts German-only or covers Romandie from day one is a focus decision, not a technical one.
5. **Pilot merchants.** Two or three cleaning companies willing to run suggest mode for a month in exchange for free access. Recruit during Phase 0 — the waiting time is otherwise wasted.
