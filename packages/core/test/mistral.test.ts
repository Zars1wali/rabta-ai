import { describe, it, expect, vi } from 'vitest';
import {
  MistralProviderAdapter,
  LlmProviderFactory,
  type LlmMessage
} from '../src/llm/index.js';

describe('Mistral EU Provider Adapter & Factory (WP-30)', () => {
  it('generates chat completions with tool calls using Mistral EU API format', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'cmpl-mistral-123',
        choices: [
          {
            message: {
              role: 'assistant',
              content: null,
              tool_calls: [
                {
                  id: 'call_quote_99',
                  type: 'function',
                  function: {
                    name: 'quote',
                    arguments: JSON.stringify({ skus: ['salesops_eu'] })
                  }
                }
              ]
            },
            finish_reason: 'tool_calls'
          }
        ],
        usage: {
          prompt_tokens: 120,
          completion_tokens: 25
        }
      })
    });

    const adapter = new MistralProviderAdapter({
      apiKey: 'mistral_eu_secret',
      baseUrl: 'https://api.mistral.ai/v1',
      defaultModel: 'mistral-small-latest',
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const messages: LlmMessage[] = [
      { role: 'system', content: 'You are a compliant EU AI Sales Assistant.' },
      { role: 'user', content: 'What is the price of the Europe plan?' }
    ];

    const result = await adapter.generate(messages, {
      tools: [
        {
          name: 'quote',
          description: 'Get quote for skus',
          parameters: { type: 'object', properties: { skus: { type: 'array' } } }
        }
      ]
    });

    expect(result.finishReason).toBe('tool_calls');
    expect(result.toolCalls.length).toBe(1);
    expect(result.toolCalls[0]?.name).toBe('quote');
    expect(result.toolCalls[0]?.arguments).toEqual({ skus: ['salesops_eu'] });
    expect(result.usage.inputTokens).toBe(120);
    expect(result.usage.outputTokens).toBe(25);

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.mistral.ai/v1/chat/completions',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer mistral_eu_secret',
          'Content-Type': 'application/json'
        })
      })
    );
  });

  it('factory resolves Mistral EU adapter for Europe tier and Gemini for Standard tier', () => {
    const factory = new LlmProviderFactory({
      mistralApiKey: 'test_mistral_key',
      geminiApiKey: 'test_gemini_key'
    });

    const europeAdapter = factory.createAdapterForTier('europe');
    expect(europeAdapter.providerName).toBe('mistral');
    expect((europeAdapter as MistralProviderAdapter).isEuResident).toBe(true);

    const standardAdapter = factory.createAdapterForTier('standard');
    expect(standardAdapter.providerName).toBe('gemini');

    const liteAdapter = factory.createAdapterForTier('lite');
    expect(liteAdapter.providerName).toBe('gemini');
  });
});
