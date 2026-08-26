# Prompt for Claude Opus — RABTA AI Frontend Design & Implementation Plan

Copy everything below into Opus (or Claude Design) as your task/prompt.

---

## ROLE

Act as a senior product designer and frontend architect who specializes in minimalist, premium SaaS interfaces with strong motion design. Produce both a **design implementation plan** and, where possible, **working frontend code** (React + Tailwind, or plain HTML/CSS/JS if that's the working environment) for the sections described below.

## CONTEXT — THE PRODUCT

**RABTA AI** is an AI platform for Pakistani SMEs. It acts as a business owner's AI employee — replying to customers across WhatsApp, Instagram, TikTok, and voice calls, in the owner's own tone, using their real product catalog and pricing, in Urdu/English (and later Pashto/Hindko). The pitch: even a business owner with no technical skill can turn this on and have an AI that sells like their best salesperson, 24/7.

I need a **public-facing website/frontend** that (1) explains RABTA AI to potential customers and (2) connects into the **vendor/merchant onboarding and product management experience** that already exists (or is being built) as the backend/dashboard side of the product.

## WHAT TO DESIGN — SITE STRUCTURE

### Section 1: Landing / Marketing Page
Build a landing page that answers three questions immediately, in this order:
1. **What is this?** — A clear, jargon-free explanation of RABTA AI (AI that talks to your customers like you would, everywhere they message you).
2. **Who is it for?** — Pakistani SME owners: shopkeepers, textile sellers, restaurant owners, wholesalers — people who are busy, may not be technical, and are losing sales because they can't reply fast enough.
3. **Why does it exist? (the story)** — Write a short, human origin-story section (3–5 sentences) grounded in a real, relatable moment: a business owner missing a sale because they couldn't reply to a WhatsApp message in time, multiplied across thousands of small businesses every day in Pakistan. Keep it warm and specific, not corporate. This section should feel like the emotional core of the page, not a generic "our mission" paragraph.

Include supporting sections beneath the fold: how it works (in 3–4 simple steps), the channels it covers (WhatsApp, Instagram, TikTok, voice), a "built for every industry" note, and a clear call-to-action that leads into onboarding.

### Section 2: Connection to Vendor/Merchant Onboarding
Design a clear transition/bridge from the marketing page into the **existing onboarding flow for vendors and merchants**. This should:
- Be a prominent CTA ("Get Started" / "Onboard Your Business") that a non-technical owner would understand instantly.
- Assume the onboarding page/flow already exists elsewhere in the product — design this as an entry point/handoff, not a rebuild of onboarding itself. Note clearly in your plan where this handoff occurs and what data/state should carry over (e.g. business name, industry, contact number) if the person started filling anything in on the landing page.

### Section 3: Vendor/Merchant Product Management Dashboard
Design the interface merchants use after onboarding to manage what the AI knows about their business:
- **Subscribe** — Plan selection / subscription management (simple tiered pricing display, upgrade/downgrade, payment status).
- **Create** — Add a new product: name, price, description, images, category, variants (size/color if relevant). Should feel as easy as posting to Instagram, not filling out an enterprise form.
- **Update** — Edit existing product details, quickly and inline where possible.
- **Delete** — Remove a product, with a clear confirmation step (no accidental deletions).
- **AI Auto-Sensing** — A distinct, clearly explained feature: the merchant can connect their existing **social media links (Instagram/Facebook/TikTok profile) or their WhatsApp Business catalog**, and the AI automatically scans and imports their existing products/posts as a starting catalog, which the merchant can then review, edit, or approve rather than typing everything from scratch. Design this as a guided flow: "Connect your WhatsApp Business or social profile → AI finds your products → Review & confirm → Done." Make the AI's role in this step visible and trustworthy (e.g. showing what it found, letting the owner correct anything before it goes live).

## VISUAL / UX DIRECTION

- **Style:** Minimalist and elegant — generous white space, restrained color palette, confident typography. Nothing cluttered or "startup template" generic.
- **"4D" feel:** Interpret this as a layered sense of depth and motion rather than flat, static design — subtle parallax on scroll, soft layered shadows/glassmorphism on cards, gentle micro-interactions (hover states, smooth transitions between states), and depth cues that make the interface feel alive without being distracting or gimmicky. Motion should always serve clarity, never slow the user down.
- **Light and dark mode:** Both must be fully designed, not just an inverted color filter. Define a real palette for each (background, surface, text, accent, borders) and make sure the depth/glass effects work in both — dark mode especially needs care so translucent layers don't turn muddy.
- **Accessibility & usability first:** Remember the core brand promise is that "even an old guy" can use this. Every onboarding and product-management interaction must be legible, large-touch-target-friendly, and forgiving of mistakes, even while looking premium.
- **Language consideration:** Design with Urdu/English mixed content in mind — leave room for longer text strings and consider RTL-adjacent spacing sensibilities even if the primary UI language is English/Roman Urdu.

## DELIVERABLES — IMPLEMENTATION PLAN FORMAT

Structure your output as follows:

### 1. Information architecture
Full sitemap: landing page sections in order, onboarding handoff point, dashboard pages/screens (subscription, product list, add/edit product, AI auto-sensing flow, settings).

### 2. Design system
- Color palette for light mode and dark mode (with hex values)
- Typography scale (font choices, weights, sizes for headings/body/UI text)
- Spacing/grid system
- Core components to build: buttons, cards, product cards, forms, modals (for delete confirmation), toggles (light/dark switch), navigation, the "AI found these products" review UI
- Motion/depth system: define specific, reusable effects (e.g. card hover lift + shadow, scroll-triggered fade/parallax on landing sections, glass panel styling) so it stays consistent across pages rather than one-off animations

### 3. Page-by-page breakdown
For each screen (landing page, onboarding bridge, subscribe, product list, create/edit product, AI auto-sensing flow, delete confirmation): describe layout, key UI elements, states (empty state, loading state, error state), and how light/dark mode differ if at all.

### 4. Build plan / phases
Break the frontend build into phases with concrete deliverables:
- Phase 1: Design system + landing page (static, no backend)
- Phase 2: Onboarding bridge + handoff logic
- Phase 3: Product management dashboard (CRUD) with mock/sample data
- Phase 4: AI auto-sensing flow UI (design the interface assuming a backend API for social/WhatsApp scanning exists — define the expected request/response shape you're designing against)
- Phase 5: Light/dark mode polish, responsive/mobile pass, accessibility pass

### 5. Tech recommendation
Recommend a frontend stack suited to this (e.g. React + Tailwind CSS + Framer Motion for the depth/motion system), and justify briefly. Note any component libraries that would speed this up without fighting the minimalist/elegant direction (avoid anything that looks like a generic admin template).

### 6. Working code
Where possible, produce actual code for the landing page (hero, story section, how-it-works, CTA into onboarding) and at least one dashboard screen (e.g. product list with create/edit/delete), in both light and dark mode, so I have a working starting point rather than only a spec.

## OUTPUT FORMAT

Use clear headers matching the sections above. Be specific and opinionated on visual choices (actual colors, actual spacing values, actual motion timing) rather than vague guidance like "use nice colors." Where a decision depends on information you don't have (e.g. the exact API contract for the AI auto-sensing feature, or the existing onboarding page's current design), state your assumption clearly and proceed rather than stalling.
