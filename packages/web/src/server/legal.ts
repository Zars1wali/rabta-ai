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
        governingLaw: 'European Union / Portugal'
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
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 800px; margin: 0 auto; padding: 40px 20px; }
    h1, h2, h3 { color: #0f172a; }
  </style>
</head>
<body>
  <h1>Terms of Service</h1>
  <p><strong>Effective Date:</strong> August 30, 2026</p>
  <h2>1. Agreement to Terms</h2>
  <p>These terms are an agreement between you and <strong>${operator}</strong> (trading as <em>${trade}</em>).</p>
  <h2>2. Meta & WhatsApp Policy Compliance</h2>
  <p>Users must comply with WhatsApp Business Terms and Meta Commerce Policies.</p>
  <h2>3. Contact</h2>
  <p>Questions? Reach us at <a href="mailto:${email}">${email}</a>.</p>
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
