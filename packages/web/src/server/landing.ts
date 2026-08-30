import { PRESET_SCENARIOS } from '../ui/Simulator.js';

export interface LandingPageServerOptions {
  operatorName?: string;
  brandName?: string;
  contactEmail?: string;
}

export function handleLandingPageRoute(req: Request, options?: LandingPageServerOptions): Response {
  const brand = options?.brandName || 'Nuncio by ZeroPointIntel';
  const operator = options?.operatorName || 'Nuno Miguel Pires Ribeiro';
  const email = options?.contactEmail || 'contact@zeropointintel.com';

  const acceptsJson = req.headers.get('accept')?.includes('application/json');
  if (acceptsJson) {
    return new Response(
      JSON.stringify({
        platform: brand,
        operator,
        headline: 'Every WhatsApp enquiry answered in under a minute — turned into a structured lead for your business.',
        markets: ['trades_and_services', 'ecommerce'],
        metaStatus: 'Official Meta Tech Provider (WhatsApp Cloud API)',
        compliance: {
          gdpr: 'Compliant (EU Data Residency)',
          revDSG: 'Compliant (Swiss Data Protection)',
          aiAct: 'EU AI Act Article 50 Transparent Disclosure',
          catalogIntegrity: 'Deterministic Grounding (Zero Price Hallucination)'
        },
        sampleScenarios: PRESET_SCENARIOS,
        contactEmail: email
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const initialScenario = PRESET_SCENARIOS[0] || {
    id: 'swiss_cleaning',
    label: '🇨🇭 Swiss Cleaning',
    market: 'trades',
    message: 'Grüezi! Mir bruuched e Endreinigung für e 4.5 Zimmer Wohnig.',
    lead: {
      intent: 'quote_request',
      intentLabel: 'Move-Out Deep Clean Quote',
      customerName: 'Thomas Meier',
      language: 'Swiss German → DE',
      extractedFields: { 'Service': 'Endreinigung' },
      completeness: 90,
      missingFields: [],
      suggestedAction: 'Propose Standard Package',
      aiResponse: 'Grüezi Herr Meier, vielen Dank für Ihre Anfrage!'
    }
  };

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nuncio by ZeroPointIntel — Autonomous Conversational Commerce & WhatsApp Lead Capture</title>
  <meta name="description" content="Every WhatsApp enquiry answered in under a minute — turned into a structured lead for your trade or e-commerce business. Official Meta Tech Provider.">
  <link rel="icon" type="image/svg+xml" href="/logo.svg">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #10b981;
      --primary-dark: #059669;
      --accent: #38bdf8;
      --border: rgba(255, 255, 255, 0.1);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }
    a { color: inherit; text-decoration: none; }
    .container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
    header {
      position: sticky;
      top: 0;
      background: rgba(9, 13, 22, 0.88);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      z-index: 100;
      padding: 16px 0;
    }
    .header-inner { display: flex; justify-content: space-between; align-items: center; }
    .logo-container { display: flex; align-items: center; gap: 12px; }
    .logo-text { font-size: 19px; font-weight: 800; letter-spacing: -0.02em; }
    .badge-sub { font-size: 11px; color: var(--text-muted); background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 4px; border: 1px solid var(--border); }
    .nav-links { display: flex; align-items: center; gap: 24px; }
    .nav-links a { font-size: 14px; font-weight: 500; color: #cbd5e1; transition: color 0.15s; }
    .nav-links a:hover { color: #fff; }
    .btn-primary {
      background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
      color: #fff;
      border: none;
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
      transition: all 0.15s ease;
    }
    .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.45); }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.08);
      color: #f1f5f9;
      border: 1px solid rgba(255, 255, 255, 0.18);
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .btn-secondary:hover { background: rgba(255, 255, 255, 0.12); }
    .hero { padding: 72px 0 48px 0; text-align: center; }
    .trust-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(6, 182, 212, 0.12);
      color: var(--accent);
      border: 1px solid rgba(6, 182, 212, 0.3);
      padding: 6px 16px;
      border-radius: 30px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 24px;
    }
    .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
    .hero-title {
      font-size: clamp(34px, 5.5vw, 56px);
      font-weight: 800;
      line-height: 1.15;
      letter-spacing: -0.03em;
      max-width: 980px;
      margin: 0 auto 20px auto;
    }
    .gradient-text {
      background: linear-gradient(135deg, #34d399 0%, #38bdf8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero-sub {
      font-size: 18px;
      color: var(--text-muted);
      max-width: 780px;
      margin: 0 auto 36px auto;
      line-height: 1.6;
    }
    .simulator-wrap {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      border-radius: 16px;
      border: 1px solid var(--border);
      padding: 28px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      margin-top: 24px;
      text-align: left;
    }
    .sim-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
    .chat-box { background: #0b141a; border-radius: 12px; border: 1px solid #222e35; overflow: hidden; display: flex; flex-direction: column; }
    .chat-header { background: #202c33; padding: 12px 16px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #2a3942; }
    .avatar { width: 36px; height: 36px; border-radius: 50%; background: #00a884; display: flex; align-items: center; justify-content: center; font-weight: bold; }
    .chat-body { padding: 16px; min-height: 240px; display: flex; flex-direction: column; gap: 12px; }
    .msg-in { align-self: flex-start; max-width: 85%; background: #202c33; padding: 10px 14px; border-radius: 0 12px 12px 12px; font-size: 13.5px; }
    .msg-out { align-self: flex-end; max-width: 85%; background: #005c4b; padding: 10px 14px; border-radius: 12px 0 12px 12px; font-size: 13.5px; }
    .lead-box { background: rgba(30, 41, 59, 0.7); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.12); padding: 20px; }
    .progress-bar-bg { width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; margin-bottom: 16px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background: var(--primary); border-radius: 3px; width: 90%; transition: width 0.4s ease; }
    .field-row { display: flex; justify-content: space-between; font-size: 12.5px; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 6px; margin-bottom: 6px; }
    .field-key { color: var(--text-muted); }
    .field-val { font-weight: 600; color: #f1f5f9; text-align: right; }
    .section-title { font-size: 32px; font-weight: 800; letter-spacing: -0.02em; text-align: center; margin-bottom: 12px; }
    .section-sub { font-size: 16px; color: var(--text-muted); text-align: center; max-width: 640px; margin: 0 auto 48px auto; }
    .card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 14px; padding: 28px; }
    footer { border-top: 1px solid var(--border); background: #070a10; padding: 48px 0 32px 0; margin-top: 80px; }
    .footer-inner { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px; font-size: 13px; color: var(--text-muted); }
  </style>
</head>
<body>

  <!-- Header -->
  <header>
    <div class="container header-inner">
      <div class="logo-container">
        <div style="width: 36px; height: 36px; border-radius: 8px; background: linear-gradient(135deg, #0284c7 0%, #10b981 100%); display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px rgba(2, 132, 199, 0.4); border: 1px solid rgba(255, 255, 255, 0.2); flex-shrink: 0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div>
          <span class="logo-text">Nuncio</span>
          <span class="badge-sub">by ZeroPointIntel</span>
        </div>
      </div>
      <nav class="nav-links">
        <a href="#solutions">Solutions</a>
        <a href="#simulator">Live Simulator</a>
        <a href="#compliance">Compliance</a>
        <a href="#portfolio">Engineering</a>
        <a href="/privacy" style="color: var(--text-muted);">Privacy</a>
        <button class="btn-primary" onclick="alert('Welcome to Nuncio! WhatsApp Embedded Signup is available in your tenant dashboard.')">Start Free Trial</button>
      </nav>
    </div>
  </header>

  <!-- Hero Section -->
  <section class="hero container">
    <div class="trust-pill">
      <div class="pulse-dot"></div>
      Official Meta Tech Provider • WhatsApp Cloud API
    </div>
    <h1 class="hero-title">
      Every WhatsApp inquiry qualified and closed in under a minute — <span class="gradient-text">autonomously &amp; 24/7.</span>
    </h1>
    <p class="hero-sub">
      78% of customers buy from the first business that responds. Nuncio is the autonomous WhatsApp AI commercial engine that qualifies inbound leads, quotes verified prices with zero hallucination, and collects payments — keeping business owners in 1-tap mobile control.
    </p>

    <!-- Interactive Simulator -->
    <div id="simulator" class="simulator-wrap">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 20px;">
        <div>
          <span style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 20px; text-transform: uppercase;">
            Live WhatsApp-to-Lead Simulator
          </span>
          <h3 style="font-size: 20px; font-weight: 700; margin-top: 6px;">How It Works: Inbound Inquiry → Verified Quote → 1-Tap Close</h3>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button class="btn-secondary" style="font-size: 12px; padding: 6px 12px;" onclick="loadScenario('b2b_consulting')">💼 B2B &amp; Pro Services</button>
          <button class="btn-secondary" style="font-size: 12px; padding: 6px 12px;" onclick="loadScenario('field_services')">🛠️ Field Services &amp; Trades</button>
          <button class="btn-secondary" style="font-size: 12px; padding: 6px 12px;" onclick="loadScenario('ecommerce_order')">🛍️ E-Commerce (1-Click Pay)</button>
          <button class="btn-secondary" style="font-size: 12px; padding: 6px 12px;" onclick="loadScenario('clinic_booking')">🏥 Clinics &amp; Bookings</button>
        </div>
      </div>

      <div class="sim-grid">
        <!-- WhatsApp Customer Chat View -->
        <div class="chat-box">
          <div class="chat-header">
            <div class="avatar" id="sim-avatar">E</div>
            <div>
              <div style="font-size: 14px; font-weight: 600; color: #e9edef;" id="sim-cust-name">${initialScenario.lead.customerName}</div>
              <div style="font-size: 11px; color: #8696a0;">Inbound Client • WhatsApp Chat</div>
            </div>
          </div>
          <div class="chat-body">
            <div class="msg-in">
              <div style="font-size: 11px; font-weight: 600; color: #94a3b8; margin-bottom: 2px;">Inbound Voice / Text Message:</div>
              <div id="sim-msg-text">${initialScenario.message}</div>
              <span style="font-size: 10px; color: #8696a0; display: block; margin-top: 4px;">10:42 AM</span>
            </div>
            <div class="msg-out">
              <div style="font-size: 11px; font-weight: 700; color: #25d366; margin-bottom: 4px;">🤖 Nuncio Autonomous Assistant</div>
              <div id="sim-ai-resp">${initialScenario.lead.aiResponse}</div>
              <span style="font-size: 10px; color: #8696a0; display: block; margin-top: 4px; text-align: right;">10:42 AM • ✓✓ Instant &lt; 60s Reply</span>
            </div>
          </div>
          <div style="padding: 12px; background: #202c33; border-top: 1px solid #2a3942;">
            <label style="font-size: 11px; color: #8696a0; display: block; margin-bottom: 4px;">Or type any customer inquiry to test live:</label>
            <input type="text" id="custom-sim-input" placeholder="e.g. We need ongoing compliance advisory for 20 seats starting next month..." style="width: 100%; background: #2a3942; border: none; border-radius: 6px; padding: 8px 10px; color: #fff; font-size: 13px;" oninput="handleCustomInput(this.value)">
          </div>
        </div>

        <!-- Calculated Quote & Owner Control Card -->
        <div class="lead-box">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div>
              <span style="font-size: 11px; color: #38bdf8; text-transform: uppercase; font-weight: 700;">Grounded Commercial Quote</span>
              <h4 style="font-size: 17px; font-weight: 800; color: #fff; margin-top: 2px;" id="sim-lead-title">${initialScenario.lead.intentLabel}</h4>
            </div>
            <div id="sim-score-badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; border-radius: 20px; padding: 4px 12px; font-size: 12px; font-weight: 700;">
              Ready for Approval
            </div>
          </div>
          
          <div id="sim-fields-container" style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 12px; border: 1px solid rgba(255,255,255,0.06);">
            <div class="field-row"><span class="field-key">👤 Client:</span><span class="field-val">Elena Rossi (Nexus Capital AG)</span></div>
            <div class="field-row"><span class="field-key">📦 Service Tier:</span><span class="field-val">Standard Advisory (15–50 seats)</span></div>
            <div class="field-row"><span class="field-key">📍 Location & Term:</span><span class="field-val">Zurich City • 12-Month Commitment</span></div>
            <div class="field-row"><span class="field-key">✨ Deliverables:</span><span class="field-val">Monthly audits &amp; &lt; 2h SLA response</span></div>
            <div class="field-row" style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px; margin-top: 6px;"><span class="field-key" style="font-weight: 700; color: #38bdf8;">💰 Retainer Rate:</span><span class="field-val" style="font-size: 16px; color: #34d399; font-weight: 800;">CHF 2'450.00 / mo</span></div>
          </div>

          <!-- Owner Mobile Alert Section -->
          <div style="background: rgba(15, 23, 42, 0.95); border: 1px solid #0284c7; border-radius: 10px; padding: 14px; margin-top: 14px;">
            <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #38bdf8; font-weight: 700; margin-bottom: 6px;">
              <span>📱</span> WhatsApp Alert on Business Owner's Mobile:
            </div>
            <div style="font-size: 12.5px; color: #e2e8f0; line-height: 1.4; background: #1e293b; padding: 8px 10px; border-radius: 6px; font-family: monospace;" id="sim-action-text">
              🔔 Neue B2B Anfrage: Elena Rossi (Nexus Capital, CHF 2'450/mo).<br>Antworte <b>/approve</b> zum Bestätigen des Termins.
            </div>
            <button class="btn-primary" style="width: 100%; font-size: 13.5px; padding: 10px; margin-top: 10px; font-weight: 700;" onclick="alert('✅ Lead Confirmed! Discovery call reservation and official retainer scope dispatched.')">
              ✓ Reply /approve (Confirm Lead &amp; Dispatch Proposal)
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Transversal Business Pillars Section -->
  <section id="solutions" class="container" style="padding: 70px 0;">
    <h2 class="section-title">Solving the Core Inbound Problems for Any Business</h2>
    <p class="section-sub">From local service pros and medical clinics to high-growth e-commerce and professional consulting firms.</p>
    <div class="card-grid">
      <div class="card">
        <div style="font-size: 28px; margin-bottom: 12px;">⚡</div>
        <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 8px;">Instant Speed-to-Lead (&lt; 60s)</h3>
        <p style="font-size: 14px; color: var(--text-muted);">
          Never lose high-value inbound customers during evenings, weekends, or busy workdays. Instant AI engagement before leads look elsewhere.
        </p>
      </div>
      <div class="card">
        <div style="font-size: 28px; margin-bottom: 12px;">🔒</div>
        <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 8px;">Zero Price Hallucination</h3>
        <p style="font-size: 14px; color: var(--text-muted);">
          Strictly bound to your verified catalog rates, service packages, and SLA parameters. Zero unauthorized discounts or fake commitments.
        </p>
      </div>
      <div class="card">
        <div style="font-size: 28px; margin-bottom: 12px;">📱</div>
        <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 8px;">1-Tap WhatsApp Mobile Control</h3>
        <p style="font-size: 14px; color: var(--text-muted);">
          High-ticket quotes and commitments require your 1-tap confirmation right inside WhatsApp. Zero complex CRM portals to open while on the go.
        </p>
      </div>
      <div class="card">
        <div style="font-size: 28px; margin-bottom: 12px;">💳</div>
        <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 8px;">Frictionless In-Chat Payments</h3>
        <p style="font-size: 14px; color: var(--text-muted);">
          Turn conversations into immediate bank deposits with 1-click Stripe, Twint, and SEPA payment links generated directly in chat.
        </p>
      </div>
      <div class="card">
        <div style="font-size: 28px; margin-bottom: 12px;">🎙️</div>
        <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 8px;">Voice Notes &amp; Multilingual Parsing</h3>
        <p style="font-size: 14px; color: var(--text-muted);">
          Transcribes audio voice notes and translates colloquial dialects across German, French, Italian, and English into structured orders.
        </p>
      </div>
      <div class="card">
        <div style="font-size: 28px; margin-bottom: 12px;">🛡️</div>
        <h3 style="font-size: 18px; font-weight: 700; margin-bottom: 8px;">Swiss revDSG &amp; EU AI Act Compliance</h3>
        <p style="font-size: 14px; color: var(--text-muted);">
          Official Meta Tech Provider with automated Article 50 AI disclosure, strict PostgreSQL tenant RLS, and 1-click data deletion.
        </p>
      </div>
    </div>
  </section>

  <!-- Compliance Section -->
  <section id="compliance" style="background: #0d131f; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 80px 0;">
    <div class="container">
      <h2 class="section-title">Swiss &amp; European Trust Center</h2>
      <p class="section-sub">Engineered to comply strictly with Swiss revDSG, European GDPR, and EU AI Act Article 50.</p>
      <div class="card-grid">
        <div class="card" style="background: rgba(255,255,255,0.02);">
          <h4 style="color: var(--accent); font-size: 16px; margin-bottom: 8px;">Meta Tech Provider</h4>
          <p style="font-size: 13.5px; color: var(--text-muted);">Direct official integration via Meta Cloud API with merchant-owned numbers and zero third-party scrapers.</p>
        </div>
        <div class="card" style="background: rgba(255,255,255,0.02);">
          <h4 style="color: var(--primary); font-size: 16px; margin-bottom: 8px;">EU AI Act Art. 50</h4>
          <p style="font-size: 13.5px; color: var(--text-muted);">Clear automated disclosure ensuring every customer knows they are interacting with an AI assistant.</p>
        </div>
        <div class="card" style="background: rgba(255,255,255,0.02);">
          <h4 style="color: #a78bfa; font-size: 16px; margin-bottom: 8px;">Swiss revDSG &amp; GDPR</h4>
          <p style="font-size: 13.5px; color: var(--text-muted);">Tenant Row-Level Security isolation in European databases with 1-click data deletion.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Engineering Pedigree Section -->
  <section id="portfolio" class="container" style="padding: 80px 0;">
    <h2 class="section-title">ZeroPointIntel Engineering Pedigree</h2>
    <p class="section-sub">Nuncio is built upon ZeroPointIntel's high-assurance distributed systems, cybersecurity, and telemetry architecture.</p>
    <div class="card-grid">
      <div class="card">
        <h4 style="font-size: 16px; margin-bottom: 8px;">Sub-100ms Ingress</h4>
        <p style="font-size: 13.5px; color: var(--text-muted);">High-throughput webhook pipelines with HMAC-SHA256 signature verification and BullMQ Redis deduplication.</p>
      </div>
      <div class="card">
        <h4 style="font-size: 16px; margin-bottom: 8px;">Deterministic Price Verification</h4>
        <p style="font-size: 13.5px; color: var(--text-muted);">AI is strictly grounded in the database offering catalog — zero price hallucination or unverified discounts.</p>
      </div>
      <div class="card">
        <h4 style="font-size: 16px; margin-bottom: 8px;">Owner Control Plane</h4>
        <p style="font-size: 13.5px; color: var(--text-muted);">Money-moving transitions require 1-tap owner approval via WhatsApp or web dashboard.</p>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer>
    <div class="container footer-inner">
      <div style="display: flex; align-items: center; gap: 10px;">
        <div style="width: 24px; height: 24px; border-radius: 6px; background: linear-gradient(135deg, #0284c7 0%, #10b981 100%); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <span>© 2026 <strong>ZeroPointIntel</strong> (${operator}). All rights reserved.</span>
      </div>
      <div style="display: flex; gap: 20px;">
        <a href="/privacy">Privacy Policy</a>
        <a href="/terms">Terms of Service</a>
        <a href="/dpa">Data Processing Agreement</a>
        <a href="/privacy#user-data-deletion">Data Deletion</a>
      </div>
    </div>
  </footer>

  <script>
    const scenarios = ${JSON.stringify(PRESET_SCENARIOS)};

    function loadScenario(id) {
      const sc = scenarios.find(s => s.id === id) || scenarios[0];
      document.getElementById('sim-avatar').innerText = sc.lead.customerName.charAt(0);
      document.getElementById('sim-cust-name').innerText = sc.lead.customerName;
      document.getElementById('sim-msg-text').innerText = sc.message;
      document.getElementById('sim-ai-resp').innerText = sc.lead.aiResponse;
      document.getElementById('sim-lead-title').innerText = sc.lead.intentLabel;
      document.getElementById('sim-score-badge').innerText = 'Ready for Approval';
      document.getElementById('sim-action-text').innerHTML = '🔔 Neue Anfrage: ' + sc.lead.customerName + '<br>Antworte <b>/approve</b> zum Bestätigen.';

      let fieldsHtml = '<div class="field-row"><span class="field-key">👤 Client:</span><span class="field-val">' + sc.lead.customerName + '</span></div>';
      for (const [k, v] of Object.entries(sc.lead.extractedFields)) {
        fieldsHtml += '<div class="field-row"><span class="field-key">• ' + k + ':</span><span class="field-val">' + v + '</span></div>';
      }
      document.getElementById('sim-fields-container').innerHTML = fieldsHtml;
    }

    function handleCustomInput(val) {
      if (!val || val.length < 3) return;
      const isConsulting = /consult|retainer|advisory|legal|audit|agency|b2b/i.test(val);
      const isEmergency = /urgent|notfall|leak|broken|repair|kaputt|heute|today|error|fault/i.test(val);
      const isEcommerce = /order|buy|commander|stock|shipping|livraison|bouteille|price/i.test(val);
      
      let title = isConsulting ? 'Professional Advisory Quote (CHF 2\'450/mo)' : (isEmergency ? 'Emergency Specialist Dispatch (CHF 280.00)' : (isEcommerce ? 'E-Commerce Order Draft (CHF 63.90)' : 'Commercial Service Lead'));
      
      document.getElementById('sim-msg-text').innerText = val;
      document.getElementById('sim-lead-title').innerText = title;
      document.getElementById('sim-score-badge').innerText = 'Ready for Approval';
      document.getElementById('sim-ai-resp').innerText = isConsulting 
        ? 'Hello! Based on your requirements, our standard advisory rate is CHF 250.– / hour. Would you like to schedule an introductory discovery call?'
        : (isEmergency ? 'We have prioritized your emergency request. Our standard diagnostic fee is CHF 280.–. A specialist can be dispatched within 2 hours. Should we confirm?' : 'Thank you for reaching out! We have checked our verified catalog and prepared the quote details for you.');
      
      document.getElementById('sim-fields-container').innerHTML = 
        '<div class="field-row"><span class="field-key">📋 Request Scope:</span><span class="field-val">' + title + '</span></div>' +
        '<div class="field-row"><span class="field-key">📝 Inbound Text:</span><span class="field-val">' + val.slice(0, 50) + '...</span></div>' +
        '<div class="field-row" style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px; margin-top: 6px;"><span class="field-key" style="font-weight: 700; color: #38bdf8;">💰 Rate / Quote:</span><span class="field-val" style="font-size: 16px; color: #34d399; font-weight: 800;">' + (isConsulting ? 'CHF 2\'450 / mo' : (isEmergency ? 'CHF 280.00' : 'CHF 63.90')) + '</span></div>';
      
      document.getElementById('sim-action-text').innerHTML = '🔔 Neue Offerte für Kunden.<br>Antworte <b>/approve</b> zum Senden.';
    }
  </script>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}
