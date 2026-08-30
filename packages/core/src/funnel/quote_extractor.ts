export interface ExtractedTradeQuote {
  serviceType?: 'move_out_deep_clean' | 'regular_maintenance' | 'window_cleaning' | 'emergency_repair' | 'office_cleaning' | 'other';
  propertyType?: 'flat' | 'house' | 'office' | 'commercial';
  rooms?: number;
  squareMeters?: number;
  frequency?: 'one_off' | 'weekly' | 'bi_weekly' | 'monthly';
  location?: string;
  targetDate?: string;
  hasBalcony?: boolean;
  hasBlinds?: boolean;
  handoverGuarantee?: boolean;
  rawNotes?: string;
  completeness: number; // 0.0 to 1.0
  missingFields: string[];
  suggestedQuoteMinor?: number; // Grounded price estimate in minor units
  currency: string;
}

export interface QuoteFieldWeights {
  serviceType: number;
  propertyScope: number; // rooms or m2
  location: number;
  targetDate: number;
}

export class TradeQuoteExtractor {
  private weights: QuoteFieldWeights = {
    serviceType: 0.25,
    propertyScope: 0.25,
    location: 0.25,
    targetDate: 0.25
  };

  /**
   * Normalizes Swiss German dialect words into standard business concepts.
   */
  normalizeSwissGerman(text: string): string {
    return text
      .replace(/\b(chuchi|chuchichäschtli)\b/gi, 'küche')
      .replace(/\b(zügle|züglet|umzügle)\b/gi, 'umzug')
      .replace(/\b(abnahm|abnahmegarantie|abgabegarantie)\b/gi, 'handover guarantee')
      .replace(/\b(fäischter|feischter|fänschter)\b/gi, 'fenster')
      .replace(/\b(wohig|wohnig|wohning)\b/gi, 'wohnung')
      .replace(/\b(sturze|storen|lamelle)\b/gi, 'blinds')
      .replace(/\b(bad|badi|badezimmer)\b/gi, 'badezimmer')
      .replace(/\b(grüezi|hoi|sali|guten tag)\b/gi, 'hello');
  }

  /**
   * Extracts structured trade parameters from inbound conversation messages.
   */
  extractFromText(text: string, currency = 'CHF'): ExtractedTradeQuote {
    const normalized = this.normalizeSwissGerman(text);
    const lower = normalized.toLowerCase();

    // 1. Service Type
    let serviceType: ExtractedTradeQuote['serviceType'] = undefined;
    let handoverGuarantee = false;

    if (/end of tenancy|move out|endreinigung|umzugsreinigung|wohnungsreinigung|umzug|abgabe|handover/i.test(lower)) {
      serviceType = 'move_out_deep_clean';
      handoverGuarantee = /handover guarantee|abnahme|abgabegarantie|garantie/i.test(lower);
    } else if (/unterhalt|regular|maintenance|weekly|bi-weekly|wöchentlich/i.test(lower)) {
      serviceType = 'regular_maintenance';
    } else if (/fenster|window|storen|blinds/i.test(lower)) {
      serviceType = 'window_cleaning';
    } else if (/notfall|emergency|rohrbruch|leak|plumbing|sanitär/i.test(lower)) {
      serviceType = 'emergency_repair';
    } else if (/büro|office|commercial/i.test(lower)) {
      serviceType = 'office_cleaning';
    } else if (/reinigung|clean/i.test(lower)) {
      serviceType = 'move_out_deep_clean';
    }

    // 2. Property Type
    let propertyType: ExtractedTradeQuote['propertyType'] = undefined;
    if (/flat|wohnung|apartment|zimmer/i.test(lower)) {
      propertyType = 'flat';
    } else if (/house|haus|villa|einfamilienhaus/i.test(lower)) {
      propertyType = 'house';
    } else if (/büro|office/i.test(lower)) {
      propertyType = 'office';
    }

    // 3. Rooms
    let rooms: number | undefined = undefined;
    const roomMatch = lower.match(/(\d+(?:\.\d+)?)\s*(?:-|\s)?(?:bed|bedroom|zimmer|zi\b|rooms?)/i);
    if (roomMatch && roomMatch[1]) {
      rooms = parseFloat(roomMatch[1]);
    }

    // 4. Square Meters
    let squareMeters: number | undefined = undefined;
    const m2Match = lower.match(/(\d{2,4})\s*(?:m2|qm|m²|square meters?)/i);
    if (m2Match && m2Match[1]) {
      squareMeters = parseInt(m2Match[1], 10);
    }

    // 5. Frequency
    let frequency: ExtractedTradeQuote['frequency'] = undefined;
    if (/einmalig|one-off|single|einzeln/i.test(lower)) {
      frequency = 'one_off';
    } else if (/wöchentlich|weekly/i.test(lower)) {
      frequency = 'weekly';
    } else if (/alle 2 wochen|bi-weekly|fortnightly/i.test(lower)) {
      frequency = 'bi_weekly';
    } else if (/monatlich|monthly/i.test(lower)) {
      frequency = 'monthly';
    } else if (serviceType === 'move_out_deep_clean' || serviceType === 'emergency_repair') {
      frequency = 'one_off';
    }

    // 6. Location
    let location: string | undefined = undefined;
    const locMatch = text.match(/\b(8\d{3}|zürich|zurich|winterthur|basel|bern|geneva|genève|lausanne|lucerne|luzern|zug|st\.?\s*gallen)\b/i);
    if (locMatch && locMatch[0]) {
      location = locMatch[0].trim();
    }

    // 7. Target Date (prioritize explicit calendar dates over relative words)
    let targetDate: string | undefined = undefined;
    const explicitDate = text.match(/\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mär|mar|apr|mai|may|jun|jul|aug|sep|okt|oct|nov|dez|dec)[a-z]*|(?:jan|feb|mär|mar|apr|mai|may|jun|jul|aug|sep|okt|oct|nov|dez|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}\.\s*(?:jan|feb|mär|mar|apr|mai|may|jun|jul|aug|sep|okt|oct|nov|dez|dec)[a-z]*|\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2}))/i);
    const relativeDate = text.match(/\b(hüt|today|morgen|tomorrow)\b/i);
    if (explicitDate && explicitDate[0]) {
      targetDate = explicitDate[0].trim();
    } else if (relativeDate && relativeDate[0]) {
      targetDate = relativeDate[0].trim();
    }

    // 8. Addons
    const hasBalcony = /balkon|balcony|terrasse|terrace/i.test(lower);
    const hasBlinds = /storen|blinds|lamellen/i.test(lower);

    // 9. Calculate Completeness and Missing Fields
    let score = 0;
    const missingFields: string[] = [];

    if (serviceType) {
      score += this.weights.serviceType;
    } else {
      missingFields.push('service_type');
    }

    // For emergency repair, property scope is optional / implied
    if (serviceType === 'emergency_repair') {
      score += this.weights.propertyScope;
    } else if (rooms !== undefined || squareMeters !== undefined || propertyType !== undefined) {
      score += this.weights.propertyScope;
    } else {
      missingFields.push('property_scope');
    }

    if (location) {
      score += this.weights.location;
    } else {
      missingFields.push('location');
    }

    if (targetDate) {
      score += this.weights.targetDate;
    } else {
      missingFields.push('target_date');
    }

    // 10. Compute Grounded Estimate (Typical Swiss Trade Rates)
    let suggestedQuoteMinor: number | undefined = undefined;
    if (serviceType === 'move_out_deep_clean') {
      if (rooms && rooms >= 3) {
        suggestedQuoteMinor = 89000; // CHF 890.00
      } else if (rooms && rooms >= 2) {
        suggestedQuoteMinor = 65000; // CHF 650.00
      } else if (rooms && rooms >= 1) {
        suggestedQuoteMinor = 45000; // CHF 450.00
      } else if (squareMeters) {
        suggestedQuoteMinor = Math.round(squareMeters * 9.5) * 100;
      }
    } else if (serviceType === 'emergency_repair') {
      suggestedQuoteMinor = 45000; // CHF 450.00 base dispatch + diagnostics
    }

    return {
      serviceType,
      propertyType,
      rooms,
      squareMeters,
      frequency,
      location,
      targetDate,
      hasBalcony,
      hasBlinds,
      handoverGuarantee,
      rawNotes: text,
      completeness: Math.min(1.0, Math.max(0.0, score)),
      missingFields,
      suggestedQuoteMinor,
      currency
    };
  }
}

export const defaultQuoteExtractor = new TradeQuoteExtractor();
