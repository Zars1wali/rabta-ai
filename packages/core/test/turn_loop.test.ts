import { describe, it, expect, vi } from 'vitest';
import { AgentTurnExecutor } from '../src/agent/turn_loop.js';
import { MockLlmProviderAdapter } from '../src/llm/mock.js';
import type {
  SessionRepository,
  MessageRepository,
  TenantRepository,
  ToolCallRepository
} from '../src/db/repositories.js';
import { REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '../src/db/seed.js';
import type { AgentMessage, AgentTurnInput } from '@salesops/types';

describe('AgentTurnExecutor Turn Loop', () => {
  const tenantId = REWILT_TENANT_ID;
  const sessionId = '550e8400-e29b-41d4-a716-446655440000';

  it('completes a 10-turn simulated conversation retaining history and updating metrics', async () => {
    const inMemoryMessages: AgentMessage[] = [];

    const mockTenantRepo = {
      getById: vi.fn().mockResolvedValue({
        id: tenantId,
        displayName: 'Rewilt Sales Ops',
        config: REWILT_TENANT_CONFIG
      })
    } as unknown as TenantRepository;

    const mockMessageRepo = {
      getRecentHistory: vi.fn().mockImplementation(async (_tId: string, _sId: string, limit = 15) => {
        return inMemoryMessages.slice(-limit);
      }),
      addMessage: vi.fn().mockImplementation(async (msg: { role: AgentMessage['role']; content: string }) => {
        const stored: AgentMessage = {
          id: crypto.randomUUID(),
          role: msg.role,
          content: msg.content,
          createdAt: new Date().toISOString()
        };
        inMemoryMessages.push(stored);
        return stored;
      })
    } as unknown as MessageRepository;

    const mockSessionRepo = {
      getSession: vi.fn().mockResolvedValue({ id: sessionId, tenantId, tokensUsed: 0, costMinor: 0 }),
      updateTurn: vi.fn().mockResolvedValue({ id: sessionId })
    } as unknown as SessionRepository;

    const mockToolCallRepo = {
      recordToolCall: vi.fn().mockResolvedValue({ id: 'tool-call-1' })
    } as unknown as ToolCallRepository;

    const mockLlm = new MockLlmProviderAdapter();

    const executor = new AgentTurnExecutor({
      llm: mockLlm,
      sessionRepo: mockSessionRepo,
      messageRepo: mockMessageRepo,
      tenantRepo: mockTenantRepo,
      toolCallRepo: mockToolCallRepo
    });

    const conversationPrompts = [
      'Olá, o que é a Rewilt?',
      'Vocês vendem soluções de atendimento?',
      'Quanto custa o plano Standard?',
      'Tem fidelização?',
      'Como funciona o suporte?',
      'E se eu quiser testar primeiro no meu catálogo?',
      'Vocês têm integração com WooCommerce?',
      'E cumprem o EU AI Act?',
      'Quais são os métodos de pagamento?',
      'Perfeito, como posso avançar?'
    ];

    // Execute 10 turns
    for (let turn = 0; turn < conversationPrompts.length; turn++) {
      const prompt = conversationPrompts[turn]!;
      const turnInput: AgentTurnInput = {
        sessionId,
        tenantId,
        message: {
          id: `msg-in-${turn}`,
          channel: 'web',
          sessionId,
          senderId: 'user-1',
          content: prompt,
          timestamp: new Date().toISOString()
        },
        history: inMemoryMessages.slice(-15),
        stage: 'discover',
        locale: 'pt-PT'
      };

      const output = await executor.executeTurn(turnInput);

      expect(output.chunks.length).toBe(1);
      expect(output.chunks[0]).toContain(`Mock reply to: "${prompt}"`);
      expect(output.usage.inputTokens).toBeGreaterThan(0);
      expect(output.usage.outputTokens).toBeGreaterThan(0);
      expect(output.usage.costMinor).toBeGreaterThanOrEqual(1);
    }

    // 10 turns × 2 messages per turn (1 visitor + 1 agent) = 20 messages stored
    expect(inMemoryMessages.length).toBe(20);

    // Verify history retrieving is called and bounded
    expect(mockMessageRepo.getRecentHistory).toHaveBeenCalledTimes(10);
    expect(mockSessionRepo.updateTurn).toHaveBeenCalledTimes(10);
  });

  it('handles server-side tool execution when LLM emits a tool call', async () => {
    const inMemoryMessages: AgentMessage[] = [];

    const mockTenantRepo = {
      getById: vi.fn().mockResolvedValue({
        id: tenantId,
        displayName: 'Rewilt Sales Ops',
        config: REWILT_TENANT_CONFIG
      })
    } as unknown as TenantRepository;

    const mockMessageRepo = {
      getRecentHistory: vi.fn().mockResolvedValue([]),
      addMessage: vi.fn().mockImplementation(async (msg: { role: AgentMessage['role']; content: string }) => {
        inMemoryMessages.push({
          id: crypto.randomUUID(),
          role: msg.role,
          content: msg.content,
          createdAt: new Date().toISOString()
        });
      })
    } as unknown as MessageRepository;

    const mockSessionRepo = {
      getSession: vi.fn().mockResolvedValue({ id: sessionId, tenantId, tokensUsed: 0, costMinor: 0 }),
      updateTurn: vi.fn().mockResolvedValue({ id: sessionId })
    } as unknown as SessionRepository;

    const mockToolCallRepo = {
      recordToolCall: vi.fn().mockResolvedValue({ id: 'tool-call-123' })
    } as unknown as ToolCallRepository;

    let callCount = 0;
    const mockLlm = new MockLlmProviderAdapter(async () => {
      callCount++;
      if (callCount === 1) {
        // First round: proposes a quote tool call
        return {
          text: '',
          toolCalls: [
            {
              id: 'call_1',
              name: 'quote',
              arguments: { sku: 'salesops_standard', quantity: 1 }
            }
          ],
          finishReason: 'TOOL_CALL',
          usage: { inputTokens: 40, outputTokens: 15 }
        };
      }
      // Second round: provides final quote statement
      return {
        text: 'O plano Standard custa 79€ por mês com 500 conversas incluídas.',
        toolCalls: [],
        finishReason: 'STOP',
        usage: { inputTokens: 60, outputTokens: 25 }
      };
    });

    const mockToolHandler = vi.fn().mockResolvedValue({
      result: { sku: 'salesops_standard', priceMinor: 7900, currency: 'EUR' },
      ok: true,
      latencyMs: 15
    });

    const executor = new AgentTurnExecutor({
      llm: mockLlm,
      sessionRepo: mockSessionRepo,
      messageRepo: mockMessageRepo,
      tenantRepo: mockTenantRepo,
      toolCallRepo: mockToolCallRepo,
      toolHandler: mockToolHandler
    });

    const turnInput: AgentTurnInput = {
      sessionId,
      tenantId,
      message: {
        id: 'msg-quote',
        channel: 'web',
        sessionId,
        senderId: 'user-1',
        content: 'Quanto custa o plano Standard?',
        timestamp: new Date().toISOString()
      },
      history: [],
      stage: 'qualify',
      locale: 'pt-PT'
    };

    const output = await executor.executeTurn(turnInput);

    expect(mockToolHandler).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'quote' }),
      expect.objectContaining({ tenantId, sessionId })
    );

    expect(mockToolCallRepo.recordToolCall).toHaveBeenCalledTimes(1);
    expect(output.toolCalls.length).toBe(1);
    expect(output.chunks[0]).toBe('O plano Standard custa 79€ por mês com 500 conversas incluídas.');
  });
});
