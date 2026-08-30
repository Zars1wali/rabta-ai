export type SupportedLanguage = 'de' | 'fr' | 'it' | 'en' | 'pt';

export interface LanguageDetectionResult {
  language: SupportedLanguage;
  isSwissGerman: boolean;
  confidence: number;
}

export class MultilingualNormalizer {
  /**
   * Detects language and Swiss German dialect markers from inbound customer text.
   */
  detectLanguage(text: string): LanguageDetectionResult {
    const lower = text.toLowerCase();

    // 1. Swiss German Dialect Markers
    const swissGermanRegex = /\b(grüezi|sali|hoi|chuchi|zügle|züglet|wohning|wohnig|fäischter|feischter|fänschter|chamer|bruuche|mues|gits|hüt|abnahm|abgabegarantie|zürich|züri|winterthur|badi)\b/i;
    const isSwissGerman = swissGermanRegex.test(lower);

    // 2. French Markers
    if (/\b(bonjour|salut|nettoyage|devis|combien|merci|appartement|pièces|urgent|s'il vous plaît|bon|cordialement)\b/i.test(lower)) {
      return { language: 'fr', isSwissGerman: false, confidence: 0.9 };
    }

    // 3. Italian Markers
    if (/\b(buongiorno|ciao|pulizia|preventivo|quanto costa|grazie|appartamento|locali|per favore)\b/i.test(lower)) {
      return { language: 'it', isSwissGerman: false, confidence: 0.9 };
    }

    // 4. English Markers
    if (/\b(hello|hi|quote|cleaning|how much|apartment|rooms|urgent|please|thanks|thank you)\b/i.test(lower) && !swissGermanRegex.test(lower)) {
      return { language: 'en', isSwissGerman: false, confidence: 0.85 };
    }

    // 5. Portuguese Markers
    if (/\b(olá|ola|bom dia|orçamento|limpeza|quanto custa|obrigado|apartamento|por favor)\b/i.test(lower)) {
      return { language: 'pt', isSwissGerman: false, confidence: 0.9 };
    }

    // Default to German (High German or Swiss German)
    return {
      language: 'de',
      isSwissGerman,
      confidence: isSwissGerman ? 0.95 : 0.8
    };
  }

  /**
   * Normalizes Swiss German Mundart into standard Hochdeutsch for precise LLM tool calling.
   */
  normalizeMundartToHochdeutsch(text: string): string {
    return text
      .replace(/\bgrüezi miteinand\b/gi, 'Guten Tag zusammen')
      .replace(/\bgrüezi\b/gi, 'Guten Tag')
      .replace(/\bsali\b/gi, 'Hallo')
      .replace(/\bhoi\b/gi, 'Hallo')
      .replace(/\bchuchi\b/gi, 'Küche')
      .replace(/\bchuchichäschtli\b/gi, 'Küchenschrank')
      .replace(/\b(zügle|züglet|umzügle)\b/gi, 'umziehen')
      .replace(/\b(abnahm|abnahmegarantie|abgabegarantie)\b/gi, 'Abnahmegarantie')
      .replace(/\b(fäischter|feischter|fänschter)\b/gi, 'Fenster')
      .replace(/\b(wohig|wohnig|wohning)\b/gi, 'Wohnung')
      .replace(/\b(sturze|storen|lamelle)\b/gi, 'Storen und Lamellen')
      .replace(/\b(badi|bad)\b/gi, 'Badezimmer')
      .replace(/\b(bruuche|brucht|mues)\b/gi, 'benötige')
      .replace(/\b(hüt)\b/gi, 'heute')
      .replace(/\b(chamer)\b/gi, 'können wir')
      .replace(/\b(züri)\b/gi, 'Zürich');
  }
}

export const defaultMultilingualNormalizer = new MultilingualNormalizer();
