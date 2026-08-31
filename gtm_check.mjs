import { spawn } from 'node:child_process';

const TEST_PORT = 3456;

console.log('================================================================');
console.log('🚀 Nuncio by ZeroPointIntel — Go-To-Market (GTM) Verification Run');
console.log('================================================================\n');

async function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function makeRequest(path, options = {}) {
  const url = `http://127.0.0.1:${TEST_PORT}${path}`;
  const response = await fetch(url, options);
  const status = response.status;
  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();
  let json = null;
  if (contentType.includes('application/json')) {
    try {
      json = JSON.parse(text);
    } catch {
      // not json
    }
  }
  return { status, text, json, contentType };
}

async function runGtmChecks() {
  console.log(`[1/5] Starting Commercial Demo Server on port ${TEST_PORT}...`);
  const serverProc = spawn('node', ['demo_server.mjs'], {
    env: { ...process.env, PORT: String(TEST_PORT) },
    stdio: 'pipe'
  });

  serverProc.stderr.on('data', (d) => {
    console.error(`[SERVER ERR]: ${d}`);
  });

  await wait(1200);

  const results = [];

  try {
    // Probe 1: Commercial Landing Page & Simulator SSR
    console.log('[2/5] Probing Landing Page SSR (GET /)...');
    const landingRes = await makeRequest('/');
    const landingOk =
      landingRes.status === 200 &&
      landingRes.text.includes('Nuncio') &&
      landingRes.text.includes('Live WhatsApp-to-Lead Simulator');
    results.push({
      test: 'Landing Page & Simulator SSR (GET /)',
      status: landingOk ? 'PASSED ✅' : 'FAILED ❌',
      code: landingRes.status
    });

    // Probe 2: Trust Center Legal Endpoints
    console.log('[3/5] Probing Trust Center & Meta Legal Compliance Endpoints...');
    const privacyRes = await makeRequest('/privacy');
    const termsRes = await makeRequest('/terms');
    const dpaRes = await makeRequest('/dpa');
    const deletionRes = await makeRequest('/data-deletion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signed_request: 'test_token' })
    });

    results.push({
      test: 'Privacy Policy (GET /privacy)',
      status: privacyRes.status === 200 ? 'PASSED ✅' : 'FAILED ❌',
      code: privacyRes.status
    });
    results.push({
      test: 'Terms of Service (GET /terms)',
      status: termsRes.status === 200 ? 'PASSED ✅' : 'FAILED ❌',
      code: termsRes.status
    });
    results.push({
      test: 'Data Processing Agreement (GET /dpa)',
      status: dpaRes.status === 200 ? 'PASSED ✅' : 'FAILED ❌',
      code: dpaRes.status
    });
    results.push({
      test: 'Meta Data Deletion Callback (POST /data-deletion)',
      status: deletionRes.status === 200 && deletionRes.json?.confirmation_code ? 'PASSED ✅' : 'FAILED ❌',
      code: deletionRes.status
    });

    // Probe 3: Meta Embedded Signup Config
    console.log('[4/5] Probing Meta Embedded Signup Config Endpoint (GET /api/waba/embedded-signup/config)...');
    const embeddedRes = await makeRequest('/api/waba/embedded-signup/config');
    const embeddedOk =
      embeddedRes.status === 200 &&
      embeddedRes.json?.appId === '1584644373301704' &&
      embeddedRes.json?.version === 'v21.0';

    results.push({
      test: 'Meta Embedded Signup Configuration (GET /api/waba/embedded-signup/config)',
      status: embeddedOk ? 'PASSED ✅' : 'FAILED ❌',
      code: embeddedRes.status,
      detail: `App ID: ${embeddedRes.json?.appId}`
    });

    // Probe 4: Live Multilingual WhatsApp Simulation & Stripe Link Engine
    console.log('[5/5] Executing Live Multilingual WhatsApp-to-Lead Simulation (POST /api/simulate)...');
    
    // 4a. Swiss German Cleaning Quote
    const simCleaning = await makeRequest('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: 'Grüezi miteinand! Ich bruuche e Endreinigung für mini 4.5 Zimmer Wohnig in Züri inkl. Chuchi und Abnahmegarantie am 15. Oktober.',
        vertical: 'swiss_cleaning'
      })
    });

    const cleanOk =
      simCleaning.status === 200 &&
      simCleaning.json?.ok === true &&
      simCleaning.json?.language?.isSwissGerman === true &&
      simCleaning.json?.quoteCalculation?.sku === 'CLEAN-MOVE-4.5R' &&
      simCleaning.json?.quoteCalculation?.totalPriceMinor === 118000 &&
      simCleaning.json?.stripeCheckoutUrl?.includes('stripe.com');

    results.push({
      test: 'Swiss German Normalization & 4.5 Zimmer Quote Calculation',
      status: cleanOk ? 'PASSED ✅' : 'FAILED ❌',
      code: simCleaning.status,
      detail: `SKU: ${simCleaning.json?.quoteCalculation?.sku} | Price: CHF ${(simCleaning.json?.quoteCalculation?.totalPriceMinor / 100).toFixed(2)} | Stripe URL Generated: ${Boolean(simCleaning.json?.stripeCheckoutUrl)}`
    });

    // 4b. Urgent HVAC Diagnostics
    const simHvac = await makeRequest('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: 'Hi, urgent sanitär notfall rohrbruch in Bern today. Please dispatch!',
        vertical: 'hvac_trades'
      })
    });

    const hvacOk =
      simHvac.status === 200 &&
      simHvac.json?.ok === true &&
      simHvac.json?.quoteCalculation?.sku === 'TRADE-EMERGENCY-DISPATCH' &&
      simHvac.json?.quoteCalculation?.totalPriceMinor === 45000;

    results.push({
      test: 'HVAC Emergency Dispatch Quoting',
      status: hvacOk ? 'PASSED ✅' : 'FAILED ❌',
      code: simHvac.status,
      detail: `SKU: ${simHvac.json?.quoteCalculation?.sku} | Price: CHF ${(simHvac.json?.quoteCalculation?.totalPriceMinor / 100).toFixed(2)}`
    });

  } finally {
    serverProc.kill('SIGTERM');
  }

  console.log('\n================================================================');
  console.log('📊 GO-TO-MARKET (GTM) ENDPOINT & SIMULATION VERIFICATION RESULTS');
  console.log('================================================================\n');

  console.table(results);

  const allPassed = results.every((r) => r.status.includes('PASSED'));
  if (allPassed) {
    console.log('\n🌟 ALL GTM CHECKS AND COMMERCIAL SANDBOXES PASSED WITH ZERO ERRORS!\n');
  } else {
    console.error('\n❌ SOME GTM CHECKS FAILED!\n');
    process.exit(1);
  }
}

runGtmChecks().catch((err) => {
  console.error('Fatal GTM check error:', err);
  process.exit(1);
});
