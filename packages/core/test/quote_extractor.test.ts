import { describe, it, expect } from 'vitest';
import { defaultQuoteExtractor } from '../src/funnel/quote_extractor.js';

describe('TradeQuoteExtractor', () => {
  const extractor = defaultQuoteExtractor;

  it('extracts complete quote fields from Zurich move-out cleaning inquiry', () => {
    const text =
      'Hi! How much for a full end-of-tenancy deep clean for a 3-bedroom flat in Zurich with handover guarantee? Handover date is Oct 15th.';
    const result = extractor.extractFromText(text);

    expect(result.serviceType).toBe('move_out_deep_clean');
    expect(result.propertyType).toBe('flat');
    expect(result.rooms).toBe(3);
    expect(result.location).toMatch(/zurich/i);
    expect(result.targetDate).toBe('Oct 15th');
    expect(result.handoverGuarantee).toBe(true);
    expect(result.completeness).toBe(1.0);
    expect(result.missingFields).toEqual([]);
    expect(result.suggestedQuoteMinor).toBe(89000); // CHF 890.00
  });

  it('normalizes Swiss German vocabulary and extracts emergency trade quote', () => {
    const text =
      'Grüezi! Sanitär Notfall Chuchi Rohrbruch bi üs z Winterthur 8400, Wasser lauft under em Spüeltrog. Chönd ihr hüt 28. Aug cho?';
    const result = extractor.extractFromText(text);

    expect(result.serviceType).toBe('emergency_repair');
    expect(result.location).toMatch(/winterthur/i);
    expect(result.targetDate).toBe('28. Aug');
    expect(result.completeness).toBe(1.0);
    expect(result.suggestedQuoteMinor).toBe(45000); // CHF 450.00
  });

  it('computes fractional completeness when fields are missing', () => {
    const text = 'Hallo, was kostet eine Wohnungsreinigung?';
    const result = extractor.extractFromText(text);

    expect(result.serviceType).toBe('move_out_deep_clean');
    expect(result.propertyType).toBe('flat');
    expect(result.completeness).toBe(0.5); // serviceType (0.25) + propertyScope (0.25)
    expect(result.missingFields).toContain('location');
    expect(result.missingFields).toContain('target_date');
  });

  it('correctly handles window and blinds addon cleaning', () => {
    const text =
      'Guten Tag, wir suchen eine Fensterreinigung inkl. Storen und Balkon für ein Haus in Zug am 12. Sept.';
    const result = extractor.extractFromText(text);

    expect(result.serviceType).toBe('window_cleaning');
    expect(result.propertyType).toBe('house');
    expect(result.hasBalcony).toBe(true);
    expect(result.hasBlinds).toBe(true);
    expect(result.location).toMatch(/zug/i);
    expect(result.targetDate).toBe('12. Sept');
    expect(result.completeness).toBe(1.0);
  });
});
