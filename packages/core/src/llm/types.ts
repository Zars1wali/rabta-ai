export type LlmMessageRole = 'system' | 'user' | 'assistant' | 'tool';

export interface LlmToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface LlmMessage {
  role: LlmMessageRole;
  content: string;
  toolCalls?: LlmToolCall[];
  toolCallId?: string;
  name?: string;
}

export interface ToolDeclaration {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface LlmGenerateOptions {
  model?: string;
  temperature?: number;
  maxOutputTokens?: number;
  tools?: ToolDeclaration[];
  signal?: AbortSignal;
}

export interface LlmGenerationChunk {
  text?: string;
  toolCalls?: LlmToolCall[];
  finishReason?: string;
  usage?: {
    inputTokens: number;
    outputTokens: number;
  };
}

export interface LlmGenerationResult {
  text: string;
  toolCalls: LlmToolCall[];
  finishReason: string;
  usage: {
    inputTokens: number;
    outputTokens: number;
  };
}

export interface LlmProviderAdapter {
  readonly providerName: string;
  generate(messages: LlmMessage[], options?: LlmGenerateOptions): Promise<LlmGenerationResult>;
  generateStream(messages: LlmMessage[], options?: LlmGenerateOptions): AsyncIterable<LlmGenerationChunk>;
}
