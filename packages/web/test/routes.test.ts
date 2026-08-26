import { describe, it, expect, vi } from 'vitest';
import {
  resolveTenantByOrigin,
  handleSessionRoute,
  handleChatRoute,
  handleHealthRoute
} from '../src/server/index.js';
import type { TenantRecord } from '../src/server/tenant_resolver.js';
import type {
  TenantRepository,
  SessionRepository,
  MessageRepository
} from '@salesops/core';
import { AgentTurnExecutor, MockLlmProviderAdapter } from '@salesops/core';
import { REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '@salesops/core';

describe('Web Server API Routes', () => {
  const mockTenant: TenantRecord = {
    id: REWILT_TENANT_ID,
    slug: 'rewilt',
    displayName: 'Rewilt Sales Ops',
    config: REWILT_TENANT_CONFIG,
    createdAt: new Date(),
    updatedAt: new Date()
  };

  const mockTenantRepo = {} as TenantRepository;

  describe('resolveTenantByOrigin', () => {
    it('returns 403 when Origin header is missing', async () => {
      const result = await resolveTenantByOrigin(null, mockTenantRepo, async () => [mockTenant]);
      expect(result.ok).toBe(false);
      expect(result.statusCode).toBe(403);
    });

    it('returns 403 when Origin is not registered in any tenant allowedOrigins', async () => {
      const result = await resolveTenantByOrigin('https://unauthorized-domain.com', mockTenantRepo, async () => [mockTenant]);
      expect(result.ok).toBe(false);
      expect(result.statusCode).toBe(403);
    });

    it('resolves tenant context for registered allowed origin', async () => {
      const result = await resolveTenantByOrigin('https://rewilt.com', mockTenantRepo, async () => [mockTenant]);
      expect(result.ok).toBe(true);
      expect(result.tenant?.id).toBe(REWILT_TENANT_ID);
      expect(result.tenant?.slug).toBe('rewilt');
    });

    it('resolves localhost development origin', async () => {
      const result = await resolveTenantByOrigin('http://localhost:3000', mockTenantRepo, async () => [mockTenant]);
      expect(result.ok).toBe(true);
      expect(result.tenant?.id).toBe(REWILT_TENANT_ID);
    });
  });

  describe('POST /api/salesops/session', () => {
    it('rejects unauthorized origin with 403 Forbidden', async () => {
      const req = new Request('http://localhost/api/salesops/session', {
        method: 'POST',
        headers: { Origin: 'https://evil.com' }
      });

      const res = await handleSessionRoute(req, {
        tenantRepo: mockTenantRepo,
        sessionRepo: {} as SessionRepository,
        messageRepo: {} as MessageRepository,
        allTenantsProvider: async () => [mockTenant]
      });

      expect(res.status).toBe(403);
      const json = await res.json();
      expect(json.ok).toBe(false);
    });

    it('creates session and returns opening greeting with EU AI Act Art. 50 disclosure for authorized origin', async () => {
      const sessionId = '00000000-0000-4000-8000-000000000099';
      const mockSessionRepo = {
        createSession: vi.fn().mockResolvedValue({
          id: sessionId,
          tenantId: REWILT_TENANT_ID,
          channel: 'web',
          stage: 'greet',
          locale: 'pt-PT'
        })
      } as unknown as SessionRepository;

      const mockMessageRepo = {
        addMessage: vi.fn().mockResolvedValue({ id: 'msg-1' })
      } as unknown as MessageRepository;

      const req = new Request('http://localhost/api/salesops/session', {
        method: 'POST',
        headers: { Origin: 'https://rewilt.com', 'Content-Type': 'application/json' },
        body: JSON.stringify({ locale: 'pt-PT' })
      });

      const res = await handleSessionRoute(req, {
        tenantRepo: mockTenantRepo,
        sessionRepo: mockSessionRepo,
        messageRepo: mockMessageRepo,
        allTenantsProvider: async () => [mockTenant]
      });

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json.ok).toBe(true);
      expect(json.sessionId).toBe(sessionId);
      expect(json.greeting).toContain('assistente de vendas');
      expect(mockMessageRepo.addMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          tenantId: REWILT_TENANT_ID,
          sessionId,
          role: 'agent'
        })
      );
    });
  });

  describe('POST /api/salesops/chat SSE stream', () => {
    it('streams tokens and done frame over SSE', async () => {
      const sessionId = '00000000-0000-4000-8000-000000000099';

      const mockLlm = new MockLlmProviderAdapter(async () => {
        return {
          text: 'O plano Standard custa 79€ por mês.',
          toolCalls: [],
          finishReason: 'STOP',
          usage: { inputTokens: 50, outputTokens: 20 }
        };
      });

      const mockMessageRepo = {
        getRecentHistory: vi.fn().mockResolvedValue([]),
        addMessage: vi.fn().mockResolvedValue({ id: 'msg-1' })
      } as unknown as MessageRepository;

      const mockSessionRepo = {
        updateTurn: vi.fn().mockResolvedValue({ id: sessionId })
      } as unknown as SessionRepository;

      const mockToolCallRepo = {
        recordToolCall: vi.fn()
      };

      const executor = new AgentTurnExecutor({
        llm: mockLlm,
        sessionRepo: mockSessionRepo,
        messageRepo: mockMessageRepo,
        tenantRepo: {
          getById: vi.fn().mockResolvedValue(mockTenant)
        } as unknown as TenantRepository,
        toolCallRepo: mockToolCallRepo as unknown as ToolCallRepository
      });

      const req = new Request('http://localhost/api/salesops/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          tenantId: REWILT_TENANT_ID,
          message: { content: 'Quanto custa o Standard?' }
        })
      });

      const res = await handleChatRoute(req, {
        executor,
        sessionRepo: mockSessionRepo
      });

      expect(res.status).toBe(200);
      expect(res.headers.get('Content-Type')).toContain('text/event-stream');

      // Read SSE stream
      const reader = res.body?.getReader();
      expect(reader).toBeDefined();

      const decoder = new TextDecoder();
      let fullStreamText = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          fullStreamText += decoder.decode(value);
        }
      }

      expect(fullStreamText).toContain('event: token');
      expect(fullStreamText).toContain('event: done');

      // Reconstruct text from SSE token frames
      const tokenMatches = [...fullStreamText.matchAll(/event: token\ndata: (\{.*?\})\n\n/g)];
      const reconstructedText = tokenMatches
        .map((m) => JSON.parse(m[1]!).text)
        .join('');

      expect(reconstructedText).toBe('O plano Standard custa 79€ por mês.');
    });
  });

  describe('GET /api/salesops/health', () => {
    it('returns status 200 with connectivity information', async () => {
      const req = new Request('http://localhost/api/salesops/health');
      const res = await handleHealthRoute(req, {
        dbPing: async () => true
      });

      expect(res.status).toBe(200);
      const json = await res.json();
      expect(json.status).toBe('ok');
      expect(json.database).toBe('connected');
    });
  });
});
