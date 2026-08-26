import type {
  AgentTurnInput,
  AgentTurnOutput,
  FunnelStage,
  ResolvedToolCall,
  AgentEvent
} from '@salesops/types';
import type { LlmProviderAdapter, LlmMessage, ToolDeclaration, LlmToolCall } from '../llm/types.js';
import type {
  SessionRepository,
  MessageRepository,
  TenantRepository,
  ToolCallRepository
} from '../db/repositories.js';
import { renderSystemPolicy } from './policy.js';
import { sanitizeReply } from './sanitizer.js';
import { defaultBudgetGuard } from '../abuse/budget_guard.js';

export type ToolExecutionHandler = (
  toolCall: LlmToolCall,
  context: { tenantId: string; sessionId: string }
) => Promise<{ result: Record<string, unknown>; ok: boolean; latencyMs: number; event?: AgentEvent }>;

export interface AgentTurnExecutorOptions {
  llm: LlmProviderAdapter;
  sessionRepo: SessionRepository;
  messageRepo: MessageRepository;
  tenantRepo: TenantRepository;
  toolCallRepo: ToolCallRepository;
  toolHandler?: ToolExecutionHandler;
  tools?: ToolDeclaration[];
}

export class AgentTurnExecutor {
  private llm: LlmProviderAdapter;
  private sessionRepo: SessionRepository;
  private messageRepo: MessageRepository;
  private tenantRepo: TenantRepository;
  private toolCallRepo: ToolCallRepository;
  private toolHandler?: ToolExecutionHandler;
  private tools: ToolDeclaration[];

  constructor(options: AgentTurnExecutorOptions) {
    this.llm = options.llm;
    this.sessionRepo = options.sessionRepo;
    this.messageRepo = options.messageRepo;
    this.tenantRepo = options.tenantRepo;
    this.toolCallRepo = options.toolCallRepo;
    this.toolHandler = options.toolHandler;
    this.tools = options.tools || [];
  }

  async executeTurn(input: AgentTurnInput): Promise<AgentTurnOutput> {
    // 1. Fetch tenant config
    const tenant = await this.tenantRepo.getById(input.tenantId);
    const tenantName = tenant?.displayName || 'Store';
    const persona = tenant?.config.persona;
    const storePolicy = tenant?.config.policy;

    // 2. Budget & Abuse Guard Check
    const session = await this.sessionRepo.getSession(input.tenantId, input.sessionId);
    if (tenant && session) {
      const budgetCheck = defaultBudgetGuard.check({
        tenantConfig: tenant.config,
        sessionTokensUsed: session.tokensUsed,
        locale: input.locale
      });

      if (!budgetCheck.allowed && budgetCheck.fallbackMessage) {
        // Persist visitor input and degraded agent reply
        await this.messageRepo.addMessage({
          tenantId: input.tenantId,
          sessionId: input.sessionId,
          role: 'visitor',
          content: input.message.content
        });

        await this.messageRepo.addMessage({
          tenantId: input.tenantId,
          sessionId: input.sessionId,
          role: 'agent',
          content: budgetCheck.fallbackMessage
        });

        await this.sessionRepo.updateTurn(input.tenantId, input.sessionId, {
          stage: 'handoff',
          tokensUsed: 0,
          costMinor: 0
        });

        return {
          chunks: [budgetCheck.fallbackMessage],
          stage: 'handoff',
          toolCalls: [],
          events: [],
          leadDelta: null,
          usage: {
            inputTokens: 0,
            outputTokens: 0,
            costMinor: 0
          }
        };
      }
    }

    // 3. Fetch last 15 history messages
    const history = await this.messageRepo.getRecentHistory(input.tenantId, input.sessionId, 15);

    // 4. Render dynamic system policy (Catalog is strictly NOT in prompt)
    const allowedTransitions: FunnelStage[] = this.getAllowedTransitions(input.stage);
    const systemPrompt = renderSystemPolicy({
      tenantName,
      stage: input.stage,
      allowedTransitions,
      localeHint: input.locale,
      persona,
      storePolicy
    });

    // 4. Assemble LLM message array
    const llmMessages: LlmMessage[] = [
      { role: 'system', content: systemPrompt },
      ...history.map((m) => ({
        role: (m.role === 'visitor' ? 'user' : 'assistant') as LlmMessage['role'],
        content: m.content
      })),
      { role: 'user', content: input.message.content }
    ];

    let totalInputTokens = 0;
    let totalOutputTokens = 0;
    const resolvedToolCalls: ResolvedToolCall[] = [];
    const events: AgentEvent[] = [];

    // 5. First LLM generation round
    let generation = await this.llm.generate(llmMessages, {
      tools: this.tools,
      temperature: 0.5,
      maxOutputTokens: 400
    });

    totalInputTokens += generation.usage.inputTokens;
    totalOutputTokens += generation.usage.outputTokens;

    // 6. Handle tool call proposal rounds (up to 2 rounds max per turn)
    let rounds = 0;
    while (generation.toolCalls && generation.toolCalls.length > 0 && rounds < 2) {
      rounds++;

      // Append assistant's tool call proposal
      llmMessages.push({
        role: 'assistant',
        content: generation.text || '',
        toolCalls: generation.toolCalls
      });

      // Execute each tool call
      for (const tc of generation.toolCalls) {
        const start = Date.now();
        let executionResult: { result: Record<string, unknown>; ok: boolean; latencyMs: number; event?: AgentEvent };

        if (this.toolHandler) {
          executionResult = await this.toolHandler(tc, {
            tenantId: input.tenantId,
            sessionId: input.sessionId
          });
        } else {
          executionResult = {
            result: { status: 'not_implemented' },
            ok: true,
            latencyMs: Date.now() - start
          };
        }

        if (executionResult.event) {
          events.push(executionResult.event);
        }

        // Record tool call in audit table
        const recorded = await this.toolCallRepo.recordToolCall({
          tenantId: input.tenantId,
          sessionId: input.sessionId,
          name: tc.name,
          input: tc.arguments,
          output: executionResult.result,
          ok: executionResult.ok,
          latencyMs: executionResult.latencyMs
        });

        resolvedToolCalls.push({
          id: recorded.id,
          name: tc.name,
          input: tc.arguments,
          output: executionResult.result,
          ok: executionResult.ok,
          latencyMs: executionResult.latencyMs
        });

        // Append tool result message
        llmMessages.push({
          role: 'tool',
          name: tc.name,
          toolCallId: tc.id,
          content: JSON.stringify(executionResult.result)
        });
      }

      // Re-invoke LLM with tool responses
      generation = await this.llm.generate(llmMessages, {
        tools: this.tools,
        temperature: 0.5,
        maxOutputTokens: 400
      });

      totalInputTokens += generation.usage.inputTokens;
      totalOutputTokens += generation.usage.outputTokens;
    }

    // 7. Sanitize final output reply
    const rawReply = generation.text || '';
    const cleanReply = sanitizeReply(rawReply);

    // 8. Persist inbound and outbound messages
    await this.messageRepo.addMessage({
      tenantId: input.tenantId,
      sessionId: input.sessionId,
      role: 'visitor',
      content: input.message.content,
      mediaUrl: input.message.mediaUrl
    });

    await this.messageRepo.addMessage({
      tenantId: input.tenantId,
      sessionId: input.sessionId,
      role: 'agent',
      content: cleanReply
    });

    // 9. Estimate cost (e.g. Gemini 3.x Flash-Lite ~ $0.25 / 1M in, $1.50 / 1M out -> cents)
    const costMinor = Math.max(1, Math.round((totalInputTokens * 0.025 + totalOutputTokens * 0.15) / 1000));

    // 10. Update session turn metrics
    await this.sessionRepo.updateTurn(input.tenantId, input.sessionId, {
      stage: input.stage,
      tokensUsed: totalInputTokens + totalOutputTokens,
      costMinor
    });

    return {
      chunks: cleanReply ? [cleanReply] : [],
      stage: input.stage,
      toolCalls: resolvedToolCalls,
      events,
      leadDelta: null,
      usage: {
        inputTokens: totalInputTokens,
        outputTokens: totalOutputTokens,
        costMinor
      }
    };
  }

  private getAllowedTransitions(currentStage: FunnelStage): FunnelStage[] {
    switch (currentStage) {
      case 'greet':
        return ['discover', 'qualify', 'present', 'close', 'handoff'];
      case 'discover':
        return ['qualify', 'present', 'objection', 'close', 'handoff'];
      case 'qualify':
        return ['present', 'objection', 'close', 'handoff'];
      case 'present':
        return ['objection', 'close', 'handoff', 'lost'];
      case 'objection':
        return ['present', 'close', 'handoff', 'lost'];
      case 'close':
        return ['won', 'objection', 'handoff', 'lost'];
      case 'won':
      case 'lost':
      case 'handoff':
        return ['greet', 'discover', 'handoff'];
      default:
        return ['greet', 'discover', 'handoff'];
    }
  }
}
