import type {
  LlmProviderAdapter,
  LlmMessage,
  LlmGenerateOptions,
  LlmGenerationResult,
  LlmGenerationChunk
} from './types.js';

export interface MockResponseHandler {
  (messages: LlmMessage[], options?: LlmGenerateOptions): LlmGenerationResult | Promise<LlmGenerationResult>;
}

export class MockLlmProviderAdapter implements LlmProviderAdapter {
  readonly providerName = 'mock';

  constructor(private handler?: MockResponseHandler) {}

  setHandler(handler: MockResponseHandler) {
    this.handler = handler;
  }

  async generate(messages: LlmMessage[], options?: LlmGenerateOptions): Promise<LlmGenerationResult> {
    if (this.handler) {
      return await this.handler(messages, options);
    }

    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    const userText = lastUserMsg?.content || '';

    // Default mock behavior
    return {
      text: `Mock reply to: "${userText}"`,
      toolCalls: [],
      finishReason: 'STOP',
      usage: {
        inputTokens: 50,
        outputTokens: 20
      }
    };
  }

  async *generateStream(messages: LlmMessage[], options?: LlmGenerateOptions): AsyncIterable<LlmGenerationChunk> {
    const result = await this.generate(messages, options);

    const words = result.text.split(' ');
    for (const word of words) {
      yield { text: `${word} ` };
    }

    if (result.toolCalls.length > 0) {
      yield { toolCalls: result.toolCalls };
    }

    yield {
      finishReason: result.finishReason,
      usage: result.usage
    };
  }
}
