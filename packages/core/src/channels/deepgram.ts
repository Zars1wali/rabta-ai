import type { Tier } from '@salesops/types';

export interface DeepgramOptions {
  apiKey?: string;
  euResidentEndpoint?: boolean;
  fetchFn?: typeof fetch;
}

export interface TranscribeAudioOptions {
  audioBuffer: Uint8Array | ArrayBuffer;
  mimetype: string;
  locale?: string;
  tier?: Tier;
}

export interface TranscribeResult {
  ok: boolean;
  transcript?: string;
  confidence?: number;
  durationSeconds?: number;
  error?: string;
  userFacingFallback?: string;
}

export class DeepgramTranscriber {
  private apiKey?: string;
  private euResidentEndpoint: boolean;
  private fetchFn: typeof fetch;

  constructor(options?: DeepgramOptions) {
    this.apiKey = options?.apiKey || process.env.DEEPGRAM_API_KEY;
    this.euResidentEndpoint = options?.euResidentEndpoint ?? false;
    this.fetchFn = options?.fetchFn || globalThis.fetch;
  }

  resolveLanguage(locale?: string): string {
    if (!locale) return 'pt';
    const clean = locale.toLowerCase().split(/[-_]/)[0] ?? 'pt';
    const supported = ['pt', 'es', 'en', 'ur', 'fr', 'de', 'it'];
    return supported.includes(clean) ? clean : 'pt';
  }

  async transcribeAudio(options: TranscribeAudioOptions): Promise<TranscribeResult> {
    // 1. Enforce Europe-Tier EU Data Residency Guard
    if (options.tier === 'europe' && !this.euResidentEndpoint) {
      return {
        ok: false,
        error: 'EU_DATA_RESIDENCY_CONSTRAINT',
        userFacingFallback:
          options.locale?.startsWith('en')
            ? 'For EU AI Act & GDPR compliance, audio processing is restricted to EU-resident endpoints. Please send your question as text.'
            : 'Por motivos de conformidade e privacidade (EU AI Act & RGPD), o processamento de notas de voz está restrito a servidores na União Europeia. Por favor, envie a sua mensagem por texto.'
      };
    }

    if (!this.apiKey) {
      return {
        ok: false,
        error: 'DEEPGRAM_API_KEY_MISSING',
        userFacingFallback: 'O assistente de voz está temporariamente indisponível. Por favor, envie por texto.'
      };
    }

    const language = this.resolveLanguage(options.locale);
    const endpoint = this.euResidentEndpoint
      ? 'https://api.eu.deepgram.com/v1/listen'
      : 'https://api.deepgram.com/v1/listen';

    const url = `${endpoint}?model=nova-3&smart_format=true&punctuate=true&language=${language}`;

    try {
      const res = await this.fetchFn(url, {
        method: 'POST',
        headers: {
          Authorization: `Token ${this.apiKey}`,
          'Content-Type': options.mimetype || 'audio/ogg; codecs=opus'
        },
        body: options.audioBuffer as unknown as BodyInit
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        return {
          ok: false,
          error: `Deepgram API error: ${res.status} ${JSON.stringify(errJson)}`
        };
      }

      const data = (await res.json()) as {
        results?: {
          channels?: Array<{
            alternatives?: Array<{
              transcript?: string;
              confidence?: number;
            }>;
          }>;
        };
        metadata?: {
          duration?: number;
        };
      };

      const alt = data.results?.channels?.[0]?.alternatives?.[0];
      const transcript = alt?.transcript?.trim();

      if (!transcript) {
        return {
          ok: false,
          error: 'EMPTY_TRANSCRIPTION',
          userFacingFallback: 'Não foi possível compreender o áudio. Pode repetir ou escrever por texto?'
        };
      }

      return {
        ok: true,
        transcript,
        confidence: alt?.confidence ?? 0.95,
        durationSeconds: data.metadata?.duration ?? 0
      };
    } catch (err: unknown) {
      return { ok: false, error: (err as Error).message };
    }
  }
}
