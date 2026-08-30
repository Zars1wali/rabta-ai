export interface LegalDocumentOptions {
  operatorName?: string;
  contactEmail?: string;
  companyTradeName?: string;
}

export function handlePrivacyPolicyRoute(req: Request, options?: LegalDocumentOptions): Response {
  const operator = options?.operatorName || 'Nuno Miguel Pires Ribeiro';
  const email = options?.contactEmail || 'privacy@zeropointintel.com';
  const trade = options?.companyTradeName || 'ZeroPointIntel / Nuncio';

  const acceptsJson = req.headers.get('accept')?.includes('application/json');
  if (acceptsJson) {
    return new Response(
      JSON.stringify({
        title: 'Privacy Policy',
        effectiveDate: '2026-08-30',
        controller: operator,
        tradeName: trade,
        contactEmail: email,
        dpaUrl: '/dpa',
        dataDeletionUrl: '/privacy#user-data-deletion',
        subProcessors: [
          'Meta Platforms Ireland Ltd. (WhatsApp Cloud API)',
          'Stripe Payments Europe, Ltd. (Payments & Billing)',
          'Google Cloud / Vertex AI (AI Inference)',
          'Mistral AI SAS (EU AI Inference)',
          'Deepgram, Inc. (Audio Transcription)'
        ]
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Privacy Policy - ${trade}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 800px; margin: 0 auto; padding: 40px 20px; }
    h1, h2, h3 { color: #0f172a; }
    code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { border: 1px solid #cbd5e1; padding: 10px; text-align: left; }
    th { background: #f8fafc; }
  </style>
</head>
<body>
  <h1>Privacy Policy</h1>
  <p><strong>Effective Date:</strong> August 30, 2026</p>
  <h2>1. Data Controller & Operator</h2>
  <p>Operated by <strong>${operator}</strong> (trading as <em>${trade}</em>). Contact: <a href="mailto:${email}">${email}</a>.</p>
  <h2>2. Scope & Roles</h2>
  <p>Under GDPR and Swiss revDSG, we act as a Data Controller for platform accounts and a Data Processor for WhatsApp messaging services managed on behalf of merchants.</p>
  <h2>3. Sub-Processors</h2>
  <table>
    <tr><th>Provider</th><th>Purpose</th><th>Data Residency</th></tr>
    <tr><td>Meta Platforms Ireland Ltd.</td><td>WhatsApp Cloud API</td><td>European Union</td></tr>
    <tr><td>Stripe Payments Europe Ltd.</td><td>Payments & Subscriptions</td><td>European Union</td></tr>
    <tr><td>Google Cloud / Vertex AI</td><td>AI Inference</td><td>European Union</td></tr>
    <tr><td>Mistral AI SAS</td><td>EU Model Inference</td><td>European Union (France)</td></tr>
    <tr><td>Deepgram, Inc.</td><td>Voice Transcription</td><td>EU / USA (SOC 2)</td></tr>
  </table>
  <h2 id="user-data-deletion">4. User Data Deletion Instructions</h2>
  <p>Users may request deletion of their data at any time by emailing <a href="mailto:${email}">${email}</a> with the subject line <em>"Data Deletion Request"</em>.</p>
</body>
</html>`;

  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

export function handleTermsOfServiceRoute(req: Request, options?: LegalDocumentOptions): Response {
  const operator = options?.operatorName || 'Nuno Miguel Pires Ribeiro';
  const email = options?.contactEmail || 'ops@zeropointintel.com';
  const trade = options?.companyTradeName || 'ZeroPointIntel / Nuncio';

  const acceptsJson = req.headers.get('accept')?.includes('application/json');
  if (acceptsJson) {
    return new Response(
      JSON.stringify({
        title: 'Terms of Service',
        effectiveDate: '2026-08-30',
        operator,
        tradeName: trade,
        contactEmail: email,
        governingLaw: 'Switzerland (Canton of Zurich)',
        liabilityCap: 'Max 3 months fees paid or CHF 500.00 (OR Art. 100)',
        humanInTheLoop: 'AI quotes are preliminary non-binding estimates; owner holds exclusive confirmation authority.',
        merchantIndemnity: 'Merchant indemnifies vendor against customer claims, catalog errors, and opt-in violations.'
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Terms of Service - ${trade}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 860px; margin: 0 auto; padding: 40px 20px; }
    h1, h2, h3 { color: #0f172a; }
    .alert-box { background: #f8fafc; border-left: 4px solid #0284c7; padding: 12px 16px; margin: 16px 0; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Terms of Service</h1>
  <p><strong>Effective Date:</strong> August 30, 2026</p>
  <p>These Terms of Service ("Terms") constitute a legally binding agreement between you ("Merchant", "Customer") and <strong>${operator}</strong> (registered Swiss Sole Trader / <em>Einzelunternehmen</em> trading as <strong>${trade}</strong>).</p>

  <h2>1. Platform Scope & Nature of AI Communications</h2>
  <p>Nuncio provides conversational lead qualification, catalog search, and customer communications infrastructure via the WhatsApp Cloud API.</p>
  <div class="alert-box">
    <strong>Non-Binding AI Estimations (Invitatio ad offerendum):</strong> All automated messages, quotations, and schedule proposals generated by the AI assistant are preliminary informational estimates. Final commercial quotes and contractual commitments strictly require the merchant owner's explicit confirmation via <code>/approve</code> or the dashboard.
  </div>

  <h2>2. Compliance with Meta & WhatsApp Policies</h2>
  <p>The Merchant agrees to comply strictly with the WhatsApp Business Terms of Service and Meta Commerce Policies. The Merchant is solely responsible for obtaining valid end-customer consent for messaging under the Swiss revDSG and EU GDPR.</p>

  <h2>3. Limitation of Liability (Swiss Code of Obligations / OR Art. 100)</h2>
  <p>To the maximum extent permitted by Swiss law (OR Art. 100 Abs. 1):</p>
  <ul>
    <li><strong>Total Liability Cap:</strong> Vendor's cumulative financial liability arising from or related to the platform is strictly capped at the total amount paid by the Merchant to Vendor in the preceding three (3) months, or CHF 500.00 (whichever is lower).</li>
    <li><strong>Exclusion of Slight Negligence:</strong> Vendor excludes all liability for slight negligence (<em>leichte Fahrlässigkeit</em>) and auxiliary persons (<em>Hilfspersonen</em>, OR Art. 101).</li>
    <li><strong>Exclusion of Consequential Damages:</strong> Vendor is not liable for lost profits (<em>entgangener Gewinn</em>), lost customer deals, business interruption, or upstream third-party service outages (Meta, Stripe, AI inference providers).</li>
  </ul>

  <h2>4. Merchant Indemnification</h2>
  <p>The Merchant agrees to indemnify, defend, and hold harmless ${operator} and ${trade} against any third-party claims, customer disputes, damages, or regulatory fines arising out of the Merchant's trade services, catalog accuracy, defective workmanship, or unsolicited messaging.</p>

  <h2>5. Governing Law & Jurisdiction</h2>
  <p>These Terms are governed exclusively by the laws of <strong>Switzerland</strong>. The exclusive place of jurisdiction for all disputes is the competent courts of the <strong>Canton of Zurich, Switzerland</strong>.</p>

  <h2>6. Contact</h2>
  <p>Questions? Contact us at <a href="mailto:${email}">${email}</a>.</p>
</body>
</html>`;

  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

export function handleDataProcessingAgreementRoute(req: Request, options?: LegalDocumentOptions): Response {
  const operator = options?.operatorName || 'Nuno Miguel Pires Ribeiro';
  const email = options?.contactEmail || 'privacy@zeropointintel.com';
  const trade = options?.companyTradeName || 'ZeroPointIntel / Nuncio';

  const acceptsJson = req.headers.get('accept')?.includes('application/json');
  if (acceptsJson) {
    return new Response(
      JSON.stringify({
        title: 'Data Processing Agreement (DPA)',
        effectiveDate: '2026-08-30',
        processor: operator,
        tradeName: trade,
        contactEmail: email,
        legalFramework: 'Swiss revDSG / EU GDPR Art. 28',
        roleAllocation: {
          merchant: 'Data Controller (Verantwortlicher)',
          vendor: 'Data Processor (Auftragsbearbeiter)'
        },
        technicalOrganizationalMeasures: [
          'TLS 1.3 encryption in transit',
          'AES-256 encryption at rest',
          'PostgreSQL Row-Level Security (RLS) tenant isolation',
          'Automated data deletion / purge endpoints'
        ]
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Data Processing Agreement (DPA) - ${trade}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 860px; margin: 0 auto; padding: 40px 20px; }
    h1, h2, h3 { color: #0f172a; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { border: 1px solid #cbd5e1; padding: 10px; text-align: left; }
    th { background: #f8fafc; }
  </style>
</head>
<body>
  <h1>Data Processing Agreement (DPA)</h1>
  <p><strong>Effective Date:</strong> August 30, 2026</p>
  <p>This Data Processing Agreement ("DPA") supplements the Terms of Service between the Merchant (<strong>Data Controller</strong>) and <strong>${operator}</strong> trading as <strong>${trade}</strong> (<strong>Data Processor</strong>) in compliance with the Swiss Federal Act on Data Protection (<em>revDSG</em>) and EU GDPR Article 28.</p>

  <h2>1. Roles and Scope of Processing</h2>
  <p>The Merchant acts as the Data Controller with respect to all customer inquiries and personal data submitted through WhatsApp. Vendor acts as a Data Processor, processing personal data solely on documented instructions from the Merchant.</p>

  <h2>2. Technical and Organizational Measures (TOMs)</h2>
  <ul>
    <li><strong>Encryption:</strong> TLS 1.3 in transit and AES-256 at rest.</li>
    <li><strong>Tenant Isolation:</strong> Strict PostgreSQL Row-Level Security (RLS) ensuring zero cross-tenant access.</li>
    <li><strong>Data Minimization & Retention:</strong> Customer transcripts are retained for 30–90 days and purged automatically upon request.</li>
  </ul>

  <h2>3. Authorized Sub-Processors</h2>
  <table>
    <tr><th>Sub-Processor</th><th>Purpose</th><th>Location</th></tr>
    <tr><td>Meta Platforms Ireland Ltd.</td><td>WhatsApp Cloud API Transport</td><td>European Union (Ireland)</td></tr>
    <tr><td>Stripe Payments Europe Ltd.</td><td>Payment Processing & Invoicing</td><td>European Union (Ireland)</td></tr>
    <tr><td>Google Cloud / Vertex AI</td><td>AI Model Inference</td><td>European Union (Frankfurt)</td></tr>
    <tr><td>Mistral AI SAS</td><td>EU Model Inference</td><td>European Union (France)</td></tr>
    <tr><td>Deepgram, Inc.</td><td>Voice Transcription</td><td>EU / USA (SOC 2)</td></tr>
  </table>

  <h2>4. Governing Law</h2>
  <p>This DPA is governed by the laws of <strong>Switzerland</strong>, with exclusive jurisdiction in the <strong>Canton of Zurich</strong>.</p>
</body>
</html>`;

  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

export async function handleUserDataDeletionCallback(req: Request): Promise<Response> {
  if (req.method === 'POST') {
    try {
      const body = await req.json().catch(() => ({}));
      const confirmationCode = `del_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      return new Response(
        JSON.stringify({
          url: `https://nuncio.zeropointintel.com/deletion-status?code=${confirmationCode}`,
          confirmation_code: confirmationCode,
          status: 'queued',
          received: body
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    } catch {
      return new Response(JSON.stringify({ error: 'Invalid deletion request payload' }), { status: 400 });
    }
  }

  return new Response(
    JSON.stringify({
      message: 'To request data deletion, send a POST request with your user ID or email privacy@zeropointintel.com'
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }
  );
}
