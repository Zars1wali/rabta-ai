import { describe, it, expect, vi } from 'vitest';
import {
  ZPI_TENANT_ID,
  ZPI_TENANT_CONFIG,
  ZPI_CATALOG,
  TenantRepository,
  CatalogRepository,
  CatalogService,
  AgentTurnExecutor,
  MockLlmProviderAdapter,
  defaultToolRegistry,
  DEFAULT_TOOL_DECLARATIONS
} from '../src/index.js';
import type {
  SessionRepository,
  MessageRepository,
  ToolCallRepository,
  LeadRepository
} from '../src/db/repositories.js';

describe('Zero-Code Second Tenant Deployment: ZeroPointIntel (WP-18)', () => {
  it('has fully valid TenantConfig adhering to Europe-tier compliance and distinct identity', () => {
    expect(ZPI_TENANT_CONFIG.tenantId).toBe(ZPI_TENANT_ID);
    expect(ZPI_TENANT_CONFIG.displayName).toBe('ZeroPointIntel Cybersecurity & AI Ops');
    expect(ZPI_TENANT_CONFIG.tier).toBe('europe');
    expect(ZPI_TENANT_CONFIG.channels[0]?.allowedOrigins).toContain('https://zeropointintel.com');
    expect(ZPI_TENANT_CONFIG.compliance.aiDisclosure).toBe(true);
    expect(ZPI_TENANT_CONFIG.limits.tokenBudgetPerSession).toBe(60000);
  });

  it('provisions ZPI catalog items and executes search_catalog and quote without code modifications', async () => {
    const mockTenantRepo = {
      getById: vi.fn().mockImplementation(async (id: string) => {
        if (id === ZPI_TENANT_ID) {
          return {
            id: ZPI_TENANT_ID,
            slug: 'zeropointintel',
            displayName: ZPI_TENANT_CONFIG.displayName,
            config: ZPI_TENANT_CONFIG
          };
        }
        return null;
      })
    } as unknown as TenantRepository;

    const mockCatalogRepo = {
      getActiveSnapshot: vi.fn().mockResolvedValue({
        snapshot: { id: 'snap-zpi', fetchedAt: new Date() },
        items: ZPI_CATALOG.items
      }),
      searchItems: vi.fn().mockImplementation(async (_tId: string, options: { query?: string }) => {
        if (!options.query) return ZPI_CATALOG.items;
        const q = options.query.toLowerCase();
        return ZPI_CATALOG.items.filter(
          (i) => i.name.toLowerCase().includes(q) || i.sku.toLowerCase().includes(q)
        );
      }),
      getItemBySku: vi.fn().mockImplementation(async (_tId: string, sku: string) => {
        return ZPI_CATALOG.items.find((i) => i.sku === sku) ?? null;
      })
    } as unknown as CatalogRepository;

    const catalogService = new CatalogService(mockCatalogRepo, mockTenantRepo);

    // 1. Search ZPI items
    const searchResults = await catalogService.search(ZPI_TENANT_ID, { query: 'AI Act' });
    expect(searchResults.items.length).toBe(1);
    expect(searchResults.items[0]?.sku).toBe('zpi_ai_act_audit');
    expect(searchResults.items[0]?.priceMinor).toBe(150000); // €1,500.00

    // 2. Fetch ZPI item by SKU
    const itemResult = await catalogService.getBySku(ZPI_TENANT_ID, 'zpi_ai_act_audit');
    expect(itemResult.item?.priceMinor).toBe(150000);
    expect(itemResult.item?.currency).toBe('EUR');

    // 3. Turn execution using ZPI persona
    const mockSessionRepo = {
      getSession: vi.fn().mockResolvedValue({
        id: 'session-zpi-1',
        tenantId: ZPI_TENANT_ID,
        tokensUsed: 0
      }),
      updateTurn: vi.fn().mockResolvedValue({ id: 'session-zpi-1' })
    } as unknown as SessionRepository;

    const mockMessageRepo = {
      getRecentHistory: vi.fn().mockResolvedValue([]),
      addMessage: vi.fn().mockResolvedValue({ id: 'msg-zpi-1' })
    } as unknown as MessageRepository;

    const mockToolCallRepo = {
      recordToolCall: vi.fn().mockResolvedValue({ id: 'call-zpi-1' })
    } as unknown as ToolCallRepository;

    const mockLlm = new MockLlmProviderAdapter(async (messages) => {
      const lastTool = [...messages].reverse().find((m) => m.role === 'tool');
      if (lastTool) {
        return {
          text: 'The comprehensive EU AI Act Article 50 & 52 audit is priced at 1500.00 EUR with a 48h turnaround time.',
          toolCalls: [],
          finishReason: 'STOP',
          usage: { inputTokens: 50, outputTokens: 25 }
        };
      }
      return {
        text: '',
        toolCalls: [{ id: 'call_quote', name: 'quote', arguments: { skus: ['zpi_ai_act_audit'] } }],
        finishReason: 'TOOL_CALL',
        usage: { inputTokens: 50, outputTokens: 25 }
      };
    });

    const executor = new AgentTurnExecutor({
      llm: mockLlm,
      sessionRepo: mockSessionRepo,
      messageRepo: mockMessageRepo,
      tenantRepo: mockTenantRepo,
      toolCallRepo: mockToolCallRepo,
      tools: DEFAULT_TOOL_DECLARATIONS,
      toolHandler: async (toolCall, ctx) => {
        const output = await defaultToolRegistry.execute(toolCall, {
          tenantId: ctx.tenantId,
          sessionId: ctx.sessionId,
          catalogService,
          sessionRepo: mockSessionRepo,
          leadRepo: {} as unknown as LeadRepository,
          tenantRepo: mockTenantRepo,
          toolCallRepo: mockToolCallRepo
        });
        return {
          result: output.result,
          ok: output.ok,
          latencyMs: 5,
          event: output.event
        };
      }
    });

    const turn = await executor.executeTurn({
      tenantId: ZPI_TENANT_ID,
      sessionId: 'session-zpi-1',
      message: {
        role: 'user',
        content: 'How much does the EU AI Act audit cost?'
      }
    });

    const replyText = turn.chunks.join(' ');
    expect(replyText).toContain('1500.00 EUR');
    expect(replyText).toContain('EU AI Act');
  });
});
