export interface VerticalQuoteParameter {
  rooms?: number;
  squareMeters?: number;
  serviceType: string;
  handoverGuarantee?: boolean;
  frequency?: string;
  hasBalcony?: boolean;
  hasBlinds?: boolean;
  urgency?: 'normal' | 'urgent_24h' | 'weekend';
}

export interface GroundedQuoteCalculation {
  sku: string;
  title: string;
  basePriceMinor: number;
  addonPriceMinor: number;
  totalPriceMinor: number;
  currency: string;
  breakdown: string[];
  serviceDurationHours: number;
  includesHandoverGuarantee: boolean;
}

export interface VerticalPackDefinition {
  id: string;
  name: string;
  defaultCurrency: string;
  calculateQuote(params: VerticalQuoteParameter): GroundedQuoteCalculation;
  getSuggestedQuestions(missingFields: string[], language: string): string[];
}

/**
 * Swiss Cleaning Vertical Pack:
 * Standard market rates in Zürich / Swiss Romandie / Basel.
 * Formula:
 * - 1.5 - 2.5 Zimmer (bis 60m²): CHF 650
 * - 3.5 Zimmer (bis 90m²): CHF 890
 * - 4.5 Zimmer (bis 120m²): CHF 1'180
 * - 5.5+ Zimmer (ab 120m²): CHF 1'450
 * - Abnahmegarantie (Handover Guarantee): +CHF 150 (included by default in deep cleans)
 * - Balkon / Terrasse: +CHF 80
 * - Storen / Lamellen: +CHF 120
 */
export const SwissCleaningVerticalPack: VerticalPackDefinition = {
  id: 'swiss_cleaning',
  name: 'Swiss Cleaning & Umzugsreinigung',
  defaultCurrency: 'CHF',
  calculateQuote(params: VerticalQuoteParameter): GroundedQuoteCalculation {
    let sku = 'CLEAN-MOVE-GENERIC';
    let title = 'Endreinigung mit Abnahmegarantie';
    let basePriceMinor = 65000; // CHF 650.00
    let hours = 6;
    const breakdown: string[] = [];

    const rooms = params.rooms || (params.squareMeters ? params.squareMeters / 25 : 3.5);

    if (rooms >= 5.0) {
      sku = 'CLEAN-MOVE-5.5R';
      title = 'Endreinigung 5.5+ Zimmer mit Abnahmegarantie';
      basePriceMinor = 145000; // CHF 1,450.00
      hours = 12;
      breakdown.push('Grundreinigung 5.5+ Zimmer: CHF 1\'450.00');
    } else if (rooms >= 4.0) {
      sku = 'CLEAN-MOVE-4.5R';
      title = 'Endreinigung 4.5 Zimmer mit Abnahmegarantie';
      basePriceMinor = 118000; // CHF 1,180.00
      hours = 9;
      breakdown.push('Grundreinigung 4.5 Zimmer: CHF 1\'180.00');
    } else if (rooms >= 3.0) {
      sku = 'CLEAN-MOVE-3.5R';
      title = 'Endreinigung 3.5 Zimmer mit Abnahmegarantie';
      basePriceMinor = 89000; // CHF 890.00
      hours = 7;
      breakdown.push('Grundreinigung 3.5 Zimmer: CHF 890.00');
    } else {
      sku = 'CLEAN-MOVE-2.5R';
      title = 'Endreinigung 1.5 - 2.5 Zimmer mit Abnahmegarantie';
      basePriceMinor = 65000; // CHF 650.00
      hours = 5;
      breakdown.push('Grundreinigung 1.5 - 2.5 Zimmer: CHF 650.00');
    }

    let addonPriceMinor = 0;

    if (params.hasBalcony) {
      addonPriceMinor += 8000; // CHF 80.00
      breakdown.push('Balkon / Terrasse Grundreinigung: CHF 80.00');
    }

    if (params.hasBlinds) {
      addonPriceMinor += 12000; // CHF 120.00
      breakdown.push('Lamellenstoren Tiefenreinigung: CHF 120.00');
    }

    if (params.urgency === 'urgent_24h' || params.urgency === 'weekend') {
      addonPriceMinor += 20000; // CHF 200.00
      breakdown.push('Express / Wochenende Zuschlag: CHF 200.00');
    }

    const totalPriceMinor = basePriceMinor + addonPriceMinor;

    return {
      sku,
      title,
      basePriceMinor,
      addonPriceMinor,
      totalPriceMinor,
      currency: 'CHF',
      breakdown,
      serviceDurationHours: hours,
      includesHandoverGuarantee: true
    };
  },

  getSuggestedQuestions(missingFields: string[], language = 'de'): string[] {
    const questions: string[] = [];

    for (const field of missingFields) {
      if (field === 'property_scope') {
        if (language === 'fr') {
          questions.push('Combien de pièces (ou m²) comporte le logement à nettoyer?');
        } else if (language === 'en') {
          questions.push('How many rooms (or square meters) does the property have?');
        } else {
          questions.push('Wie viele Zimmer oder wie viel m² hat die Wohnung?');
        }
      } else if (field === 'location') {
        if (language === 'fr') {
          questions.push('Dans quelle ville ou code postal se situe le logement?');
        } else if (language === 'en') {
          questions.push('In which city or postal code is the property located?');
        } else {
          questions.push('In welcher Ortschaft oder PLZ befindet sich das Objekt?');
        }
      } else if (field === 'target_date') {
        if (language === 'fr') {
          questions.push('Pour quelle date souhaitez-vous effectuer le nettoyage?');
        } else if (language === 'en') {
          questions.push('What is your desired date for the cleaning?');
        } else {
          questions.push('An welchem Wunschdatum soll die Reinigung stattfinden?');
        }
      }
    }

    return questions;
  }
};

/**
 * HVAC & Emergency Trades Vertical Pack:
 */
export const HvacTradesVerticalPack: VerticalPackDefinition = {
  id: 'hvac_trades',
  name: 'HVAC, Sanitär & Handwerker Notfall',
  defaultCurrency: 'CHF',
  calculateQuote(params: VerticalQuoteParameter): GroundedQuoteCalculation {
    let basePriceMinor = 25000; // CHF 250.00 Diagnostics & Base Trip
    const breakdown = ['Anfahrt & Diagnose Grundpauschale: CHF 250.00'];

    if (params.urgency === 'urgent_24h') {
      basePriceMinor = 45000; // CHF 450.00 Emergency 24/7 Dispatch
      breakdown.push('24/7 Notfalleinsatz-Zuschlag: CHF 200.00');
    }

    return {
      sku: 'TRADE-EMERGENCY-DISPATCH',
      title: 'Notfall-Einsatz & Fehlerdiagnose vor Ort',
      basePriceMinor,
      addonPriceMinor: 0,
      totalPriceMinor: basePriceMinor,
      currency: 'CHF',
      breakdown,
      serviceDurationHours: 2,
      includesHandoverGuarantee: false
    };
  },

  getSuggestedQuestions(missingFields: string[], language = 'de'): string[] {
    const questions: string[] = [];
    for (const field of missingFields) {
      if (field === 'location') {
        questions.push(
          language === 'fr'
            ? 'Où devons-nous intervenir d\'urgence (adresse / ville)?'
            : 'Wo ist der Einsatzort (Adresse / Ortschaft)?'
        );
      }
    }
    return questions;
  }
};

export const VERTICAL_PACKS: Record<string, VerticalPackDefinition> = {
  swiss_cleaning: SwissCleaningVerticalPack,
  hvac_trades: HvacTradesVerticalPack
};

export function getVerticalPack(packId?: string): VerticalPackDefinition {
  return VERTICAL_PACKS[packId || 'swiss_cleaning'] || SwissCleaningVerticalPack;
}
