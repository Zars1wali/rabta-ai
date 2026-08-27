import type {
  LlmProviderAdapter,
  LlmMessage,
  LlmGenerateOptions,
  LlmGenerationResult,
  LlmGenerationChunk,
  LlmToolCall
} from './types.js';

export interface MistralAdapterConfig {
  apiKey: string;
  defaultModel?: string;
  baseUrl?: string; // Default: "https://api.mistral.ai/v1" (EU Resident in Paris/Frankfurt)
  timeoutMs?: number;
  maxRetries?: number;
  fetchFn?: typeof fetch;
}

export class MistralProviderAdapter implements LlmProviderAdapter {
  readonly providerName = 'mistral';
  readonly isEuResident = true; // Non-negotiable EU Data Residency flag

  private apiKey: string;
  private defaultModel: string;
  private baseUrl: string;
  private timeoutMs: number;
  private maxRetries: number;
  private fetchFn: typeof fetch;

  constructor(config: MistralAdapterConfig) {
    this.apiKey = config.apiKey;
    this.defaultModel = config.defaultModel || 'mistral-small-latest';
    this.baseUrl = config.baseUrl || 'https://api.mistral.ai/v1';
    this.timeoutMs = config.timeoutMs ?? 20000;
    this.maxRetries = config.maxRetries ?? 2;
    this.fetchFn = config.fetchFn || globalThis.fetch;
  }

  async generate(messages: LlmMessage[], options?: LlmGenerateOptions): Promise<LlmGenerationResult> {
    const model = options?.model || this.defaultModel;
    const body = this.buildRequestBody(messages, options, false);

    let lastError: Error | null = null;
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeoutMs);

        const url = `${this.baseUrl}/chat/completions`;
        const response = await this.fetchFn(url, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model,
            ...body
          }),
          signal: options?.signal || controller.signal
        });

        clearTimeout(timer);

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Mistral API error ${response.status} ${response.statusText}: ${errorText}`);
        }

        const data = (await response.json()) as Record<string, unknown>;
        return this.parseMistralResponse(data);
      } catch (err: unknown) {
        lastError = err as Error;
        if (attempt < this.maxRetries) {
          const backoffMs = Math.pow(attempt + 1, 2) * 500;
          await new Promise((res) => setTimeout(res, backoffMs));
        }
      }
    }

    throw new Error(`Mistral generate failed after ${this.maxRetries + 1} attempts. Last error: ${lastError?.message}`);
  }

  async *generateStream(messages: LlmMessage[], options?: LlmGenerateOptions): AsyncIterable<LlmGenerationChunk> {
    const model = options?.model || this.defaultModel;
    const body = this.buildRequestBody(messages, options, true);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    const url = `${this.baseUrl}/chat/completions`;
    const response = await this.fetchFn(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model,
        ...body
      }),
      signal: options?.signal || controller.signal
    });

    clearTimeout(timer);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Mistral stream error ${response.status} ${response.statusText}: ${errorText}`);
    }

    if (!response.body) {
      throw new Error('Mistral API returned an empty stream response body');
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
              const data = JSON.parse(jsonStr) as Record<string, unknown>;
              const chunk = this.parseMistralChunk(data);
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

  private buildRequestBody(messages: LlmMessage[], options?: LlmGenerateOptions, stream = false) {
    const formattedMessages = messages.map((m) => {
      if (m.role === 'assistant') {
        const msgObj: Record<string, unknown> = {
          role: 'assistant',
          content: m.content || null
        };
        if (m.toolCalls && m.toolCalls.length > 0) {
          msgObj.tool_calls = m.toolCalls.map((tc) => ({
            id: tc.id,
            type: 'function',
            function: {
              name: tc.name,
              arguments: JSON.stringify(tc.arguments)
            }
          }));
        }
        return msgObj;
      }

      if (m.role === 'tool') {
        return {
          role: 'tool',
          name: m.name,
          tool_call_id: m.toolCallId || m.name || 'unknown_tool',
          content: m.content
        };
      }

      return {
        role: m.role,
        content: m.content
      };
    });

    const body: Record<string, unknown> = {
      messages: formattedMessages,
      temperature: options?.temperature ?? 0.5,
      max_tokens: options?.maxOutputTokens ?? 400,
      stream
    };

    if (options?.tools && options.tools.length > 0) {
      body.tools = options.tools.map((t) => ({
        type: 'function',
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters
        }
      }));
    }

    return body;
  }

  private parseMistralResponse(data: Record<string, unknown>): LlmGenerationResult {
    const choices = (data.choices as Record<string, unknown>[]) || [];
    const choice = choices[0];
    const message = (choice?.message as Record<string, unknown>) || {};
    const text = (message.content as string) || '';

    const toolCalls: LlmToolCall[] = [];
    const rawToolCalls = (message.tool_calls as Record<string, unknown>[]) || [];

    for (const rtc of rawToolCalls) {
      const fn = (rtc.function as { name: string; arguments: string }) || {};
      let args: Record<string, unknown> = {};
      try {
        args = typeof fn.arguments === 'string' ? JSON.parse(fn.arguments) : (fn.arguments || {});
      } catch {
        args = {};
      }

      toolCalls.push({
        id: (rtc.id as string) || `call_${crypto.randomUUID().slice(0, 8)}`,
        name: fn.name || 'unknown',
        arguments: args
      });
    }

    const usage = (data.usage as Record<string, number>) || {};

    return {
      text,
      toolCalls,
      finishReason: (choice?.finish_reason as string) || 'stop',
      usage: {
        inputTokens: usage.prompt_tokens || 0,
        outputTokens: usage.completion_tokens || 0
      }
    };
  }

  private parseMistralChunk(data: Record<string, unknown>): LlmGenerationChunk {
    const choices = (data.choices as Record<string, unknown>[]) || [];
    const choice = choices[0];
    const delta = (choice?.delta as Record<string, unknown>) || {};
    const text = (delta.content as string) || undefined;

    const toolCalls: LlmToolCall[] = [];
    const rawToolCalls = (delta.tool_calls as Record<string, unknown>[]) || [];

    for (const rtc of rawToolCalls) {
      const fn = (rtc.function as { name?: string; arguments?: string }) || {};
      let args: Record<string, unknown> = {};
      try {
        args = typeof fn.arguments === 'string' ? JSON.parse(fn.arguments) : (fn.arguments || {});
      } catch {
        args = {};
      }

      if (fn.name) {
        toolCalls.push({
          id: (rtc.id as string) || `call_${crypto.randomUUID().slice(0, 8)}`,
          name: fn.name,
          arguments: args
        });
      }
    }

    const usage = (data.usage as Record<string, number>) || {};

    return {
      text,
      toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
      finishReason: (choice?.finish_reason as string) || undefined,
      usage: usage.prompt_tokens ? {
        inputTokens: usage.prompt_tokens,
        outputTokens: usage.completion_tokens || 0
      } : undefined
    };
  }
}
