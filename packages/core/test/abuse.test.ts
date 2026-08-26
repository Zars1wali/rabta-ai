import { describe, it, expect, vi } from 'vitest';
import {
  SessionBudgetGuard,
  SlidingWindowRateLimiter
} from '../src/abuse/index.js';
import { AgentTurnExecutor } from '../src/agent/turn_loop.js';
import { MockLlmProviderAdapter } from '../src/llm/mock.js';
import { REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '../src/db/seed.js';
import type {
  SessionRepository,
  MessageRepository,
  TenantRepository,
  ToolCallRepository
} from '../src/db/repositories.js';
import type { AgentTurnInput } from '@salesops/types';

describe('Abuse Layer & Session Budget Guardrails (WP-10)', () => {
  const guard = new SessionBudgetGuard();
  const tenantConfig = REWILT_TENANT_CONFIG;

  describe('SessionBudgetGuard', () => {
    it('allows turns within normal session token budget', () => {
      const res = guard.check({
        tenantConfig,
        sessionTokensUsed: 15000
      });

      expect(res.allowed).toBe(true);
      expect(res.sessionTokenBudget).toBe(40000);
    });

    it('gracefully triggers static FAQ & handoff when session exceeds 40k token budget', () => {
      const res = guard.check({
        tenantConfig,
        sessionTokensUsed: 42000,
        locale: 'pt-PT'
      });

      expect(res.allowed).toBe(false);
      expect(res.reason).toBe('token_budget_exceeded');
      expect(res.degradeAction).toBe('static_faq_handoff');
      expect(res.fallbackMessage).toBeDefined();
      expect(res.fallbackMessage).toContain('limite de mensagens automatizadas');
      expect(res.fallbackMessage).toContain('comercial@rewilt.com');
    });

    it('triggers degradation when monthly spend cap is exceeded', () => {
      const res = guard.check({
        tenantConfig,
        sessionTokensUsed: 5000,
        // 25 EUR limit = 2500 minor units. Pass 2600 minor units.
        monthlySpendMinor: 2600,
        locale: 'pt-PT'
      });

      expect(res.allowed).toBe(false);
      expect(res.reason).toBe('monthly_spend_cap_exceeded');
    });
  });

  describe('SlidingWindowRateLimiter', () => {
    it('allows requests within rate limit and throttles when limit is exceeded', () => {
      const limiter = new SlidingWindowRateLimiter();
      const ip = '192.168.1.100';
      const now = Date.now();

      // Send 5 requests with limit 5
      for (let i = 0; i < 5; i++) {
        const result = limiter.isAllowed(ip, 5, 60, now + i * 100);
        expect(result.allowed).toBe(true);
      }

      // 6th request should be throttled
      const throttled = limiter.isAllowed(ip, 5, 60, now + 600);
      expect(throttled.allowed).toBe(false);
      expect(throttled.remaining).toBe(0);
      expect(throttled.resetMs).toBeGreaterThan(0);
    });
  });

  describe('Turn Loop Degradation Integration', () => {
    it('gracefully degrades turn loop without invoking LLM when budget is exhausted', async () => {
      const sessionId = '00000000-0000-4000-8000-000000000099';
      const mockLlm = new MockLlmProviderAdapter();
      const llmGenerateSpy = vi.spyOn(mockLlm, 'generate');

      const mockSessionRepo = {
        getSession: vi.fn().mockResolvedValue({
          id: sessionId,
          tenantId: REWILT_TENANT_ID,
          tokensUsed: 45000 // EXHAUSTED (limit 40k)
        }),
        updateTurn: vi.fn().mockResolvedValue({ id: sessionId })
      } as unknown as SessionRepository;

      const mockMessageRepo = {
        getRecentHistory: vi.fn().mockResolvedValue([]),
        addMessage: vi.fn().mockResolvedValue({ id: 'msg-1' })
      } as unknown as MessageRepository;

      const mockTenantRepo = {
        getById: vi.fn().mockResolvedValue({
          id: REWILT_TENANT_ID,
          displayName: 'Rewilt Sales Ops',
          config: REWILT_TENANT_CONFIG
        })
      } as unknown as TenantRepository;

      const executor = new AgentTurnExecutor({
        llm: mockLlm,
        sessionRepo: mockSessionRepo,
        messageRepo: mockMessageRepo,
        tenantRepo: mockTenantRepo,
        toolCallRepo: {} as unknown as ToolCallRepository
      });

      const turnInput: AgentTurnInput = {
        sessionId,
        tenantId: REWILT_TENANT_ID,
        message: {
          id: 'msg-budget-test',
          channel: 'web',
          sessionId,
          senderId: 'user-1',
          content: 'Quero saber mais sobre os planos.',
          timestamp: new Date().toISOString()
        },
        history: [],
        stage: 'discover',
        locale: 'pt-PT'
      };

      const output = await executor.executeTurn(turnInput);

      // Asserts clean degradation without errors
      expect(output.stage).toBe('handoff');
      expect(output.chunks.length).toBe(1);
      expect(output.chunks[0]).toContain('limite de mensagens automatizadas');
      expect(output.usage.inputTokens).toBe(0);
      expect(output.usage.outputTokens).toBe(0);

      // LLM MUST NOT have been called (saving tokens and spend)
      expect(llmGenerateSpy).not.toHaveBeenCalled();

      // Session stage updated to handoff
      expect(mockSessionRepo.updateTurn).toHaveBeenCalledWith(
        REWILT_TENANT_ID,
        sessionId,
        expect.objectContaining({ stage: 'handoff' })
      );
    });
  });
});
