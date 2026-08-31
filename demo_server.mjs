import http from 'node:http';
import { handleLandingPageRoute } from './packages/web/dist/server/landing.js';
import { handlePrivacyPolicyRoute, handleTermsOfServiceRoute, handleDataProcessingAgreementRoute, handleUserDataDeletionCallback } from './packages/web/dist/server/legal.js';
import { handleEmbeddedSignupConfigRoute, handleEmbeddedSignupCallbackRoute } from './packages/web/dist/server/embedded_signup.js';
import { defaultQuoteExtractor } from './packages/core/dist/funnel/quote_extractor.js';
import { SwissCleaningVerticalPack, HvacTradesVerticalPack, getVerticalPack } from './packages/core/dist/funnel/vertical_packs.js';
import { defaultMultilingualNormalizer } from './packages/core/dist/funnel/multilingual_normalizer.js';
import { StripeBillingService } from './packages/core/dist/billing/service.js';

const PORT = process.env.PORT || 3333;
const stripeService = new StripeBillingService();

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost:3000'}`);
  const pathname = url.pathname;

  // 1. Landing Page & Live Simulator SSR
  if (pathname === '/' || pathname === '/index.html') {
    const webReq = new Request(`http://${req.headers.host || 'localhost:3000'}${req.url}`, {
      method: req.method,
      headers: req.headers
    });
    const webRes = handleLandingPageRoute(webReq, {
      brandName: 'Nuncio by ZeroPointIntel',
      operatorName: 'Nuno Miguel Pires Ribeiro',
      contactEmail: 'contact@zeropointintel.com'
    });

    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    const body = await webRes.text();
    res.end(body);
    return;
  }

  // 2. Legal Trust Center
  if (pathname === '/privacy') {
    const webReq = new Request(`http://${req.headers.host || 'localhost:3000'}${req.url}`, { method: req.method, headers: req.headers });
    const webRes = handlePrivacyPolicyRoute(webReq);
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    res.end(await webRes.text());
    return;
  }
  if (pathname === '/terms') {
    const webReq = new Request(`http://${req.headers.host || 'localhost:3000'}${req.url}`, { method: req.method, headers: req.headers });
    const webRes = handleTermsOfServiceRoute(webReq);
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    res.end(await webRes.text());
    return;
  }
  if (pathname === '/dpa') {
    const webReq = new Request(`http://${req.headers.host || 'localhost:3000'}${req.url}`, { method: req.method, headers: req.headers });
    const webRes = handleDataProcessingAgreementRoute(webReq);
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    res.end(await webRes.text());
    return;
  }
  if (pathname === '/data-deletion') {
    const webReq = new Request(`http://${req.headers.host || 'localhost:3000'}${req.url}`, { method: req.method, headers: req.headers });
    const webRes = await handleUserDataDeletionCallback(webReq);
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    res.end(await webRes.text());
    return;
  }

  // 3. Meta Embedded Signup Endpoints
  if (pathname === '/api/waba/embedded-signup/config') {
    const webReq = new Request(`http://${req.headers.host || 'localhost:3000'}${req.url}`, { method: req.method, headers: req.headers });
    const webRes = await handleEmbeddedSignupConfigRoute(webReq);
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    res.end(await webRes.text());
    return;
  }

  // 4. Live WhatsApp Simulator Processing API
  if (pathname === '/api/simulate' && req.method === 'POST') {
    let bodyText = '';
    req.on('data', (chunk) => { bodyText += chunk; });
    req.on('end', async () => {
      try {
        const { message, vertical = 'swiss_cleaning', ownerPhone = '+41 79 000 00 00' } = JSON.parse(bodyText || '{}');
        
        // 1. Language Detection & Swiss German Normalization
        const langDetection = defaultMultilingualNormalizer.detectLanguage(message || '');
        const normalizedText = defaultMultilingualNormalizer.normalizeMundartToHochdeutsch(message || '');
        
        // 2. Quote Extraction
        const extracted = defaultQuoteExtractor.extractFromText(message || '', 'CHF');
        
        // 3. Vertical Pack Deterministic Pricing
        const pack = getVerticalPack(vertical);
        const quoteCalc = pack.calculateQuote({
          rooms: extracted.rooms,
          squareMeters: extracted.squareMeters,
          serviceType: extracted.serviceType || 'move_out_deep_clean',
          handoverGuarantee: extracted.handoverGuarantee,
          hasBalcony: extracted.hasBalcony,
          hasBlinds: extracted.hasBlinds,
          urgency: extracted.serviceType === 'emergency_repair' ? 'urgent_24h' : undefined
        });

        // 4. Generate Stripe Checkout URL
        const leadId = `lead_${Math.random().toString(36).slice(2, 10)}`;
        const stripeSession = await stripeService.createTradeQuoteCheckoutSession({
          tenantId: 'tenant_demo',
          leadId,
          amountMinor: quoteCalc.totalPriceMinor,
          currency: 'CHF',
          title: quoteCalc.title
        });

        // 5. Build Owner Alert Preview
        const priceFormatted = (quoteCalc.totalPriceMinor / 100).toFixed(2);
        const ownerAlert = [
          `🔔 *Neue Offerten-Anfrage (Swiss Clean Pro)*`,
          `Kunde: Thomas Meier (+41 79 123 45 67)`,
          `• Objekt: ${extracted.rooms ? `${extracted.rooms} Zimmer` : 'Wohnung'} in ${extracted.location || 'Zürich'}`,
          `• Datum: ${extracted.targetDate || 'Nach Vereinbarung'}`,
          `• Garantie: ${quoteCalc.includesHandoverGuarantee ? 'Abnahmegarantie inkl.' : 'Standard'}`,
          `• Berechneter Richtpreis: *CHF ${priceFormatted}* (${quoteCalc.sku})`,
          '',
          `Antworte direkt mit:`,
          `*/approve ${leadId.slice(0, 8)}* - Offerte direkt freigeben & senden`,
          `*/override ${leadId.slice(0, 8)} 1250* - Preis anpassen`,
          `*/handoff ${leadId.slice(0, 8)}* - Gespräch selbst übernehmen`
        ].join('\n');

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          ok: true,
          input: message,
          language: langDetection,
          normalizedHochdeutsch: normalizedText,
          extractedFields: extracted,
          quoteCalculation: quoteCalc,
          ownerWhatsAppNotification: ownerAlert,
          stripeCheckoutUrl: stripeSession.checkoutUrl
        }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // Fallback 404
  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

server.listen(PORT, () => {
  console.log(`\n🚀 Nuncio Live Commercial Demo Server running on http://localhost:${PORT}`);
  console.log(`• Landing Page & Simulator: http://localhost:${PORT}/`);
  console.log(`• Swiss/EU Trust Center:   http://localhost:${PORT}/privacy`);
  console.log(`• Live Simulation API:     POST http://localhost:${PORT}/api/simulate\n`);
});
