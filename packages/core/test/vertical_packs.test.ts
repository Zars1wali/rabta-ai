import { describe, it, expect } from 'vitest';
import {
  SwissCleaningVerticalPack,
  HvacTradesVerticalPack,
  getVerticalPack,
  defaultMultilingualNormalizer
} from '../src/funnel/index.js';

describe('Milestone 4: AI Qualification, Vertical Packs & Multilingual Engine', () => {
  describe('1. Swiss Cleaning Vertical Pack & Zero Price Hallucination', () => {
    it('calculates deterministic quote for 4.5 Zimmer Wohnung with Abnahmegarantie in Zürich', () => {
      const quote = SwissCleaningVerticalPack.calculateQuote({
        serviceType: 'move_out_deep_clean',
        rooms: 4.5,
        handoverGuarantee: true,
        hasBalcony: true,
        hasBlinds: true
      });

      expect(quote.sku).toBe('CLEAN-MOVE-4.5R');
      expect(quote.basePriceMinor).toBe(118000); // CHF 1,180.00
      expect(quote.addonPriceMinor).toBe(20000); // CHF 80 (Balkon) + CHF 120 (Storen)
      expect(quote.totalPriceMinor).toBe(138000); // CHF 1,380.00
      expect(quote.currency).toBe('CHF');
      expect(quote.includesHandoverGuarantee).toBe(true);
      expect(quote.serviceDurationHours).toBe(9);
    });

    it('calculates 3.5 Zimmer base quote accurately', () => {
      const quote = SwissCleaningVerticalPack.calculateQuote({
        serviceType: 'move_out_deep_clean',
        rooms: 3.5,
        handoverGuarantee: true
      });

      expect(quote.sku).toBe('CLEAN-MOVE-3.5R');
      expect(quote.totalPriceMinor).toBe(89000); // CHF 890.00
      expect(quote.currency).toBe('CHF');
    });

    it('generates localized next questions for missing fields in German, French, and English', () => {
      const deQuestions = SwissCleaningVerticalPack.getSuggestedQuestions(['property_scope', 'location'], 'de');
      expect(deQuestions[0]).toContain('Wie viele Zimmer oder wie viel m²');
      expect(deQuestions[1]).toContain('In welcher Ortschaft oder PLZ');

      const frQuestions = SwissCleaningVerticalPack.getSuggestedQuestions(['property_scope', 'location'], 'fr');
      expect(frQuestions[0]).toContain('Combien de pièces');
      expect(frQuestions[1]).toContain('Dans quelle ville');

      const enQuestions = SwissCleaningVerticalPack.getSuggestedQuestions(['property_scope', 'target_date'], 'en');
      expect(enQuestions[0]).toContain('How many rooms');
      expect(enQuestions[1]).toContain('What is your desired date');
    });
  });

  describe('2. HVAC & Emergency Trades Vertical Pack', () => {
    it('calculates 24/7 urgent dispatch rate', () => {
      const quote = HvacTradesVerticalPack.calculateQuote({
        serviceType: 'emergency_repair',
        urgency: 'urgent_24h'
      });

      expect(quote.sku).toBe('TRADE-EMERGENCY-DISPATCH');
      expect(quote.totalPriceMinor).toBe(45000); // CHF 450.00
      expect(quote.currency).toBe('CHF');
    });
  });

  describe('3. Swiss German Mundart Normalization & Multilingual Detection', () => {
    it('detects Swiss German dialect and normalizes vocabulary to Hochdeutsch for LLM tool calling', () => {
      const rawSwissText = 'Grüezi miteinand! Ich bruuche e Endreinigung für mini 4.5 Zimmer Wohnig in Züri inkl. Chuchi und Abnahmegarantie.';
      const detection = defaultMultilingualNormalizer.detectLanguage(rawSwissText);

      expect(detection.language).toBe('de');
      expect(detection.isSwissGerman).toBe(true);

      const normalized = defaultMultilingualNormalizer.normalizeMundartToHochdeutsch(rawSwissText);
      expect(normalized).toContain('Guten Tag zusammen');
      expect(normalized).toContain('benötige');
      expect(normalized).toContain('Küche');
      expect(normalized).toContain('Zürich');
    });

    it('accurately detects French, Italian, English, and Portuguese inquiries', () => {
      expect(defaultMultilingualNormalizer.detectLanguage('Bonjour, je souhaite un devis pour un nettoyage').language).toBe('fr');
      expect(defaultMultilingualNormalizer.detectLanguage('Buongiorno, vorrei un preventivo per la pulizia').language).toBe('it');
      expect(defaultMultilingualNormalizer.detectLanguage('Hello, I need an end of tenancy cleaning quote in Zurich').language).toBe('en');
      expect(defaultMultilingualNormalizer.detectLanguage('Olá, gostaria de um orçamento para limpeza').language).toBe('pt');
    });
  });
});
