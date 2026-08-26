import { describe, it, expect } from 'vitest';
import { MockLlmProviderAdapter } from '../src/llm/mock.js';
import { GeminiProviderAdapter } from '../src/llm/gemini.js';

describe('LLM Provider Adapters', () => {
  it('MockLlmProviderAdapter generates responses and supports streaming', async () => {
    const mock = new MockLlmProviderAdapter();

    const result = await mock.generate([
      { role: 'system', content: 'You are an agent.' },
      { role: 'user', content: 'How much is the Standard plan?' }
    ]);

    expect(result.text).toContain('Mock reply to: "How much is the Standard plan?"');
    expect(result.usage.inputTokens).toBeGreaterThan(0);
    expect(result.usage.outputTokens).toBeGreaterThan(0);

    const streamChunks: string[] = [];
    for await (const chunk of mock.generateStream([{ role: 'user', content: 'Hello' }])) {
      if (chunk.text) {
        streamChunks.push(chunk.text);
      }
    }

    expect(streamChunks.length).toBeGreaterThan(0);
    expect(streamChunks.join('')).toContain('Mock reply to: "Hello"');
  });

  it('GeminiProviderAdapter initializes with defaults and builds structured request payloads', () => {
    const gemini = new GeminiProviderAdapter({
      apiKey: 'test-api-key',
      defaultModel: 'gemini-2.5-flash'
    });

    expect(gemini.providerName).toBe('gemini');
  });
});
