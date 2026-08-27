import type { Tier } from '@salesops/types';
import type { LlmProviderAdapter } from './types.js';
import { GeminiProviderAdapter } from './gemini.js';
import { MistralProviderAdapter } from './mistral.js';

export interface LlmFactoryOptions {
  geminiApiKey?: string;
  mistralApiKey?: string;
  geminiBaseUrl?: string;
  mistralBaseUrl?: string;
  fetchFn?: typeof fetch;
}

export class LlmProviderFactory {
  private geminiApiKey?: string;
  private mistralApiKey?: string;
  private geminiBaseUrl?: string;
  private mistralBaseUrl?: string;
  private fetchFn?: typeof fetch;

  constructor(options?: LlmFactoryOptions) {
    this.geminiApiKey = options?.geminiApiKey || process.env.GEMINI_API_KEY;
    this.mistralApiKey = options?.mistralApiKey || process.env.MISTRAL_API_KEY;
    this.geminiBaseUrl = options?.geminiBaseUrl;
    this.mistralBaseUrl = options?.mistralBaseUrl;
    this.fetchFn = options?.fetchFn;
  }

  createAdapterForTier(tier: Tier): LlmProviderAdapter {
    if (tier === 'europe') {
      // Non-negotiable EU Data Residency constraint
      const apiKey = this.mistralApiKey || 'mistral_eu_key_placeholder';
      return new MistralProviderAdapter({
        apiKey,
        baseUrl: this.mistralBaseUrl || 'https://api.mistral.ai/v1',
        defaultModel: 'mistral-small-latest',
        fetchFn: this.fetchFn
      });
    }

    const apiKey = this.geminiApiKey || 'gemini_key_placeholder';
    return new GeminiProviderAdapter({
      apiKey,
      baseUrl: this.geminiBaseUrl,
      defaultModel: 'gemini-2.5-flash'
    });
  }
}
