import { describe, it, expect } from 'vitest';
import { handleLandingPageRoute } from '../src/server/landing.js';
import { PRESET_SCENARIOS, parseCustomMessage } from '../src/ui/Simulator.js';

describe('Milestone 1: Commercial Sales Landing Page & Simulator', () => {
  it('serves optimized HTML landing page with 200 status and critical commercial elements', async () => {
    const req = new Request('https://zeropointintel.com/');
    const res = handleLandingPageRoute(req, {
      operatorName: 'Nuno Miguel Pires Ribeiro',
      brandName: 'Nuncio by ZeroPointIntel',
      contactEmail: 'contact@zeropointintel.com'
    });

    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toContain('text/html');

    const html = await res.text();
    // Core Value Proposition Headline
    expect(html).toContain('Every WhatsApp enquiry answered in under a minute');
    expect(html).toContain('turned into a structured lead');

    // Branding & Identity
    expect(html).toContain('Nuncio');
    expect(html).toContain('ZeroPointIntel');
    expect(html).toContain('Nuno Miguel Pires Ribeiro');

    // Meta Tech Provider & Compliance
    expect(html).toContain('Official Meta Tech Provider');
    expect(html).toContain('EU AI Act Art. 50');
    expect(html).toContain('Swiss revDSG');
    expect(html).toContain('GDPR');

    // Interactive Simulator & Presets
    expect(html).toContain('Live WhatsApp-to-Lead Simulator');
    expect(html).toContain('Thomas Meier');
    expect(html).toContain('8001 Zürich');

    // Legal Links
    expect(html).toContain('/privacy');
    expect(html).toContain('/terms');
    expect(html).toContain('/dpa');
    expect(html).toContain('/privacy#user-data-deletion');
  });

  it('serves structured JSON metadata when Accept: application/json is provided', async () => {
    const req = new Request('https://zeropointintel.com/', {
      headers: { Accept: 'application/json' }
    });
    const res = handleLandingPageRoute(req);

    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toContain('application/json');

    const data = await res.json();
    expect(data.platform).toBe('Nuncio by ZeroPointIntel');
    expect(data.metaStatus).toContain('Official Meta Tech Provider');
    expect(data.compliance.aiAct).toContain('EU AI Act Article 50');
    expect(data.compliance.catalogIntegrity).toContain('Deterministic Grounding');
    expect(data.sampleScenarios).toHaveLength(3);
    expect(data.sampleScenarios[0].id).toBe('swiss_cleaning');
  });

  it('correctly extracts and scores custom Swiss trade inquiries in the simulation parser', () => {
    const result = parseCustomMessage(
      'Grüezi! Mir sueched e Reinigungsfirma für e 3.5 Zimmer Wohnig (85 m2) z Winterthur.'
    );

    expect(result.intent).toBe('quote_request');
    expect(result.intentLabel).toContain('Trade Service Quote Request');
    expect(result.language).toBe('German (DE)');
    expect(result.completeness).toBeGreaterThanOrEqual(80);
    expect(result.suggestedAction).toContain('Review Catalog Rate');
  });

  it('correctly classifies urgent emergency requests in the simulation parser', () => {
    const result = parseCustomMessage(
      'Urgent! We have a broken pipe leaking in our restaurant basement in Zurich today.'
    );

    expect(result.intent).toBe('emergency');
    expect(result.intentLabel).toContain('Urgent Service Dispatch');
    expect(result.completeness).toBeGreaterThanOrEqual(75);
    expect(result.suggestedAction).toContain('Notify On-Call Technician');
  });

  it('correctly classifies product / e-commerce inquiries in French', () => {
    const result = parseCustomMessage(
      'Bonjour, est-ce que vous avez ce modèle en stock svp?'
    );

    expect(result.intent).toBe('product_enquiry');
    expect(result.language).toBe('French (FR)');
    expect(result.completeness).toBeGreaterThanOrEqual(70);
  });

  it('contains valid preset scenarios with non-zero completeness scores and grounded AI responses', () => {
    expect(PRESET_SCENARIOS.length).toBeGreaterThanOrEqual(3);

    for (const sc of PRESET_SCENARIOS) {
      expect(sc.lead.completeness).toBeGreaterThan(0);
      expect(sc.lead.completeness).toBeLessThanOrEqual(100);
      expect(sc.lead.aiResponse.length).toBeGreaterThan(20);
      expect(sc.lead.suggestedAction.length).toBeGreaterThan(10);
      expect(Object.keys(sc.lead.extractedFields).length).toBeGreaterThan(0);
    }
  });
});
