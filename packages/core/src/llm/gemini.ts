import type {
  LlmProviderAdapter,
  LlmMessage,
  LlmGenerateOptions,
  LlmGenerationResult,
  LlmGenerationChunk,
  LlmToolCall
} from './types.js';

export interface GeminiAdapterConfig {
  apiKey: string;
  defaultModel?: string;
  escalationModel?: string;
  baseUrl?: string;
  timeoutMs?: number;
  maxRetries?: number;
}

export class GeminiProviderAdapter implements LlmProviderAdapter {
  readonly providerName = 'gemini';

  private apiKey: string;
  private defaultModel: string;
  private baseUrl: string;
  private timeoutMs: number;
  private maxRetries: number;

  constructor(config: GeminiAdapterConfig) {
    this.apiKey = config.apiKey;
    this.defaultModel = config.defaultModel || 'gemini-2.5-flash';
    this.baseUrl = config.baseUrl || 'https://generativelanguage.googleapis.com/v1beta';
    this.timeoutMs = config.timeoutMs ?? 20000;
    this.maxRetries = config.maxRetries ?? 2;
  }

  async generate(messages: LlmMessage[], options?: LlmGenerateOptions): Promise<LlmGenerationResult> {
    const model = options?.model || this.defaultModel;
    const body = this.buildRequestBody(messages, options);

    let lastError: Error | null = null;
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeoutMs);

        const url = `${this.baseUrl}/models/${model}:generateContent?key=${this.apiKey}`;
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: options?.signal || controller.signal
        });

        clearTimeout(timer);

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Gemini API error ${response.status} ${response.statusText}: ${errorText}`);
        }

        const data = await response.json();
        return this.parseGeminiResponse(data);
      } catch (err: unknown) {
        lastError = err as Error;
        if (attempt < this.maxRetries) {
          // Exponential backoff: 500ms, 1500ms
          const backoffMs = Math.pow(attempt + 1, 2) * 500;
          await new Promise((res) => setTimeout(res, backoffMs));
        }
      }
    }

    throw new Error(`Gemini generate failed after ${this.maxRetries + 1} attempts. Last error: ${lastError?.message}`);
  }

  async *generateStream(messages: LlmMessage[], options?: LlmGenerateOptions): AsyncIterable<LlmGenerationChunk> {
    const model = options?.model || this.defaultModel;
    const body = this.buildRequestBody(messages, options);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    const url = `${this.baseUrl}/models/${model}:streamGenerateContent?alt=sse&key=${this.apiKey}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: options?.signal || controller.signal
    });

    clearTimeout(timer);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Gemini API stream error ${response.status} ${response.statusText}: ${errorText}`);
    }

    if (!response.body) {
      throw new Error('Gemini API returned an empty stream response body');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6);
            if (jsonStr === '[DONE]') continue;

            try {
              const data = JSON.parse(jsonStr);
              const chunk = this.parseGeminiChunk(data);
              yield chunk;
            } catch {
              // Ignore unparseable SSE lines
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  private buildRequestBody(messages: LlmMessage[], options?: LlmGenerateOptions) {
    const systemMsg = messages.find((m) => m.role === 'system');
    const nonSystemMsgs = messages.filter((m) => m.role !== 'system');

    const contents = nonSystemMsgs.map((m) => {
      if (m.role === 'user') {
        return {
          role: 'user',
          parts: [{ text: m.content }]
        };
      }
      if (m.role === 'assistant') {
        const parts: Record<string, unknown>[] = [];
        if (m.content) {
          parts.push({ text: m.content });
        }
        if (m.toolCalls && m.toolCalls.length > 0) {
          for (const tc of m.toolCalls) {
            parts.push({
              functionCall: {
                name: tc.name,
                args: tc.arguments
              }
            });
          }
        }
        return {
          role: 'model',
          parts
        };
      }
      if (m.role === 'tool') {
        let parsedResponse: Record<string, unknown>;
        try {
          parsedResponse = JSON.parse(m.content);
        } catch {
          parsedResponse = { result: m.content };
        }
        return {
          role: 'function',
          parts: [
            {
              functionResponse: {
                name: m.name || 'unknown_function',
                response: parsedResponse
              }
            }
          ]
        };
      }
      return {
        role: 'user',
        parts: [{ text: m.content }]
      };
    });

    const body: Record<string, unknown> = {
      contents,
      generationConfig: {
        temperature: options?.temperature ?? 0.5,
        maxOutputTokens: options?.maxOutputTokens ?? 400
      }
    };

    if (systemMsg) {
      body.systemInstruction = {
        parts: [{ text: systemMsg.content }]
      };
    }

    if (options?.tools && options.tools.length > 0) {
      body.tools = [
        {
          functionDeclarations: options.tools.map((t) => ({
            name: t.name,
            description: t.description,
            parameters: t.parameters
          }))
        }
      ];
    }

    return body;
  }

  private parseGeminiResponse(data: Record<string, unknown>): LlmGenerationResult {
    const candidates = (data.candidates as Record<string, unknown>[]) || [];
    const candidate = candidates[0];
    const content = (candidate?.content as Record<string, unknown>) || {};
    const parts = (content.parts as Record<string, unknown>[]) || [];

    let text = '';
    const toolCalls: LlmToolCall[] = [];

    for (const part of parts) {
      if (typeof part.text === 'string') {
        text += part.text;
      }
      if (part.functionCall && typeof part.functionCall === 'object') {
        const fc = part.functionCall as { name: string; args: Record<string, unknown> };
        toolCalls.push({
          id: `call_${crypto.randomUUID().slice(0, 8)}`,
          name: fc.name,
          arguments: fc.args || {}
        });
      }
    }

    const usageMetadata = (data.usageMetadata as Record<string, number>) || {};

    return {
      text,
      toolCalls,
      finishReason: (candidate?.finishReason as string) || 'STOP',
      usage: {
        inputTokens: usageMetadata.promptTokenCount || 0,
        outputTokens: usageMetadata.candidatesTokenCount || 0
      }
    };
  }

  private parseGeminiChunk(data: Record<string, unknown>): LlmGenerationChunk {
    const candidates = (data.candidates as Record<string, unknown>[]) || [];
    const candidate = candidates[0];
    const content = (candidate?.content as Record<string, unknown>) || {};
    const parts = (content.parts as Record<string, unknown>[]) || [];

    let text = '';
    const toolCalls: LlmToolCall[] = [];

    for (const part of parts) {
      if (typeof part.text === 'string') {
        text += part.text;
      }
      if (part.functionCall && typeof part.functionCall === 'object') {
        const fc = part.functionCall as { name: string; args: Record<string, unknown> };
        toolCalls.push({
          id: `call_${crypto.randomUUID().slice(0, 8)}`,
          name: fc.name,
          arguments: fc.args || {}
        });
      }
    }

    const usageMetadata = (data.usageMetadata as Record<string, number>) || {};

    return {
      text: text || undefined,
      toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
      finishReason: (candidate?.finishReason as string) || undefined,
      usage: {
        inputTokens: usageMetadata.promptTokenCount || 0,
        outputTokens: usageMetadata.candidatesTokenCount || 0
      }
    };
  }
}
