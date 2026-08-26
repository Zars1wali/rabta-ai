# Prompt for Antigravity — RABTA AI: Requirements → Architecture → Production Deployment Plan

Copy everything below into Antigravity as your task/prompt.

---

## ROLE

Act as a senior full-stack architect and technical lead who has shipped multi-tenant, multi-channel AI SaaS products to production. Think critically, ask clarifying questions where genuinely needed, but default to making sound engineering decisions and documenting your reasoning rather than stalling on ambiguity.

## CONTEXT — THE PRODUCT

I'm building **RABTA AI**, an AI platform for Pakistani SMEs (starting with textile/retail businesses, expanding to other industries later). Core idea:

- The AI acts as the business owner's AI employee — it talks to customers exactly the way that specific business would, not like a generic chatbot.
- It must respond across **any channel a customer uses**: WhatsApp text, WhatsApp voice notes, TikTok comments/DMs, Instagram, phone calls, or even an image sent by the customer.
- It must support **multiple languages** — starting with Urdu and English, expanding to Pashto, Hindko, and eventually other languages (e.g. Chinese, for Pakistani wholesalers dealing with Chinese suppliers via WeChat).
- It must be genuinely usable by a non-technical business owner ("even an old guy") — onboarding, content upload, and setup must be extremely simple.
- The AI should know that business's catalog, pricing, and tone, act like the best salesperson in that industry, and actually drive sales — not just answer FAQs.
- The AI can also generate and upload content on the owner's behalf (video descriptions, post captions, story replies).
- Target: Pakistani SMEs first, with a "spider web" go-to-market — physical presence in each province plus nationwide marketing plus targeted industry-by-industry pitching.

## WHAT I NEED FROM YOU

Produce a complete, detailed, end-to-end technical plan, structured as follows. Don't just list options — make explicit recommendations and justify them given the constraints below (small early team, Pakistan-based market, cost-sensitive, needs to launch a real pilot fast).

### 1. Requirements breakdown
- Extract and organize functional requirements (what the system must do) and non-functional requirements (latency, uptime, scale, data residency/privacy, cost ceilings) from the product description above.
- Identify the requirements that are deceptively hard (e.g. low-resource-language voice support, TikTok automation limits, making AI replies feel human) and flag them explicitly as risk areas.
- Define what is explicitly OUT of scope for a v1/MVP, and why.

### 2. Tech stack recommendation
For each layer below, recommend a specific stack, and explain trade-offs vs. at least one alternative:
- LLM/AI orchestration layer (model choice, prompt architecture, RAG vs. fine-tuning vs. hybrid)
- Vector store / knowledge base per business
- Backend framework and language
- Database(s) — relational, vector, cache
- Messaging/queueing for async, high-volume message handling
- Channel integrations: WhatsApp Business Cloud API (or BSP), Instagram/Facebook Graph API, TikTok (and its real limitations), voice/telephony (STT/TTS providers, with specific attention to Urdu/Pashto/Hindko support)
- Frontend/dashboard framework
- Auth & multi-tenancy approach
- Hosting/cloud provider (with cost-consciousness for a Pakistan-based startup)
- CI/CD, containerization, monitoring/observability, logging
- Payments/billing (local rails: JazzCash, Easypaisa, etc.)

### 3. System architecture
- Produce a high-level architecture diagram (describe it clearly enough to draw, including all major services and data flows) covering: inbound message ingestion from every channel → routing → context retrieval (RAG) → LLM call → response generation → outbound delivery per channel → logging/analytics.
- Define the multi-tenancy model (how each business's data, prompts, and knowledge base stay isolated).
- Define how conversation state/memory is maintained per customer, per business.
- Define the content-ingestion pipeline (owner uploads video/image/post → AI generates descriptions/captions → optional auto-posting).

### 4. Data model
- Propose a core database schema (entities: businesses, users/owners, customers, conversations, messages, knowledge base items/catalog entries, prices, channels, industries, languages).
- Note where vector embeddings attach to this schema.

### 5. API design
- Define the core internal API surface (endpoints or service boundaries) needed to support the dashboard and channel integrations.
- Define the webhook contracts needed for each external channel.

### 6. Phased implementation roadmap
Break the build into concrete phases from an empty repo to a production-grade, multi-tenant deployment. For each phase, specify:
- Goal and exit criteria (how do we know this phase is "done")
- Concrete deliverables
- Estimated timeframe assuming a small team (1–2 backend/AI engineers, 1 frontend engineer, founder handling business/pilot side)
- Dependencies/blockers (e.g. WhatsApp Business API approval lead time, TikTok API access)

Structure phases roughly as: MVP definition & pilot scoping → single-channel single-industry AI brain with RAG → WhatsApp integration → owner dashboard → pilot with real businesses & iteration → voice + additional languages → additional channels (Instagram, TikTok, image-in) → multi-tenant SaaS hardening (billing, isolation, scale) → production deployment & go-to-market readiness.

### 7. Production readiness checklist
Before calling this "production grade," define requirements for:
- Security (data isolation between tenants, secrets management, API auth, rate limiting)
- Reliability (uptime targets, failover for LLM/API outages, retry logic for message delivery)
- Cost control (per-conversation LLM cost tracking, guardrails against runaway spend)
- Compliance/privacy (customer data handling, WhatsApp/Meta policy compliance, data residency considerations for a Pakistani business)
- Testing strategy (unit, integration, conversation-quality/prompt regression testing — how do you test that an AI "sounds human" and doesn't hallucinate prices?)
- Monitoring & observability (what metrics/alerts matter for an AI-driven conversational system specifically)
- Deployment pipeline (staging → production, rollback strategy for prompt/model changes)

### 8. Cost estimate
- Rough monthly infrastructure + API cost estimate at three scale points: pilot (5 businesses), early growth (50 businesses), scale (500+ businesses). Break down by LLM API costs, voice/STT/TTS costs, hosting, and third-party channel/BSP fees.

### 9. Key risks and open questions
- List the top 5–8 technical risks most likely to derail this project, ranked by severity, with a mitigation approach for each.
- List any decisions that genuinely require my input before you can finalize the plan (e.g. budget ceiling, which industry to pilot first, whether we self-host any models).

## OUTPUT FORMAT

Structure your response with clear headers matching the sections above. Be specific and opinionated — give me a plan I can hand to an engineer and start building from, not a generic overview. Where you're uncertain or where Pakistan-specific constraints (language support, payment rails, regulatory considerations) affect the recommendation, call that out explicitly.
