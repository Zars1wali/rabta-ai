import { describe, it, expect, vi } from 'vitest';
import { generateCatalogSmokeSuite, CatalogSmokeRunner } from '../src/index.js';
import type { Catalog } from '@salesops/types';
import {
  AgentTurnExecutor,
  MockLlmProviderAdapter,
  defaultToolRegistry,
  DEFAULT_TOOL_DECLARATIONS,
  REWILT_TENANT_ID,
  REWILT_TENANT_CONFIG
} from '@salesops/core';
import type {
  SessionRepository,
  MessageRepository,
  TenantRepository,
  ToolCallRepository,
  CatalogRepository,
  LeadRepository
} from '@salesops/core';
import { CatalogService } from '@salesops/core';

describe('Automated Per-Tenant Catalog Smoke Suite (WP-16)', () => {
  const tenantId = REWILT_TENANT_ID;

  const sampleCatalog: Catalog = {
    tenantId,
    sourceKind: 'woocommerce',
    fetchedAt: new Date().toISOString(),
    items: [
      {
        sku: 'CAM-01',
        name: 'Camisa Linho',
        category: 'Vestuário',
        description: 'Camisa 100% linho',
        priceMinor: 4500,
        currency: 'EUR',
        billing: 'month',
        available: true,
        attributes: {},
        url: null
      },
      {
        sku: 'CAL-02',
        name: 'Calça Jeans',
        category: 'Vestuário',
        description: 'Calça jeans azul',
        priceMinor: 6500,
        currency: 'EUR',
        billing: 'month',
        available: true,
        attributes: {},
        url: null
      },
      {
        sku: 'SAP-03',
        name: 'Sapatos Couro',
        category: 'Calçado',
        description: 'Sapatos de couro artesanais',
        priceMinor: 12000,
        currency: 'EUR',
        billing: 'month',
        available: false, // Out of stock
        attributes: {},
        url: null
      }
    ]
  };

  it('generates derived test cases covering in-stock items, out-of-stock items, and non-existent SKU probing', () => {
    const cases = generateCatalogSmokeSuite(sampleCatalog);

    // 2 in-stock price tests + 1 out-of-stock test + 1 non-existent probe = 4 cases
    expect(cases.length).toBe(4);

    const priceCase1 = cases.find((c) => c.id === 'smoke_price_CAM-01');
    expect(priceCase1).toBeDefined();
    expect(priceCase1?.expectedToolCalls).toContain('quote');
    expect(priceCase1?.requiredPhrases).toContain('CAM-01');

    const oosCase = cases.find((c) => c.id === 'smoke_oos_SAP-03');
    expect(oosCase).toBeDefined();
    expect(oosCase?.expectedToolCalls).toContain('search_catalog');

    const probeCase = cases.find((c) => c.id.startsWith('smoke_non_existent_'));
    expect(probeCase).toBeDefined();
  });

  it('runs smoke tests and passes 100% against responsive agent executor', async () => {
    const catalogService = new CatalogService(
      {
        getActiveSnapshot: vi.fn().mockResolvedValue({
          snapshot: { id: 'snap-1', fetchedAt: new Date() },
          items: sampleCatalog.items
        }),
        searchItems: vi.fn().mockImplementation(async (_tId: string, options: { query?: string }) => {
          if (!options.query) return sampleCatalog.items;
          const q = options.query.toLowerCase();
          return sampleCatalog.items.filter((i) => i.name.toLowerCase().includes(q) || i.sku.toLowerCase().includes(q));
        }),
        getItemBySku: vi.fn().mockImplementation(async (_tId: string, sku: string) => {
          return sampleCatalog.items.find((i) => i.sku === sku) ?? null;
        })
      } as unknown as CatalogRepository,
      {
        getById: vi.fn().mockResolvedValue({
          id: tenantId,
          config: REWILT_TENANT_CONFIG
        })
      } as unknown as TenantRepository
    );

    const mockSessionRepo = {
      getSession: vi.fn().mockResolvedValue({
        id: 'session-smoke',
        tenantId,
        tokensUsed: 0
      }),
      updateTurn: vi.fn().mockResolvedValue({ id: 'session-smoke' })
    } as unknown as SessionRepository;

    const mockMessageRepo = {
      getRecentHistory: vi.fn().mockResolvedValue([]),
      addMessage: vi.fn().mockResolvedValue({ id: 'msg-1' })
    } as unknown as MessageRepository;

    const mockTenantRepo = {
      getById: vi.fn().mockResolvedValue({
        id: tenantId,
        displayName: 'Rewilt Sales Ops',
        config: REWILT_TENANT_CONFIG
      })
    } as unknown as TenantRepository;

    const mockToolCallRepo = {
      recordToolCall: vi.fn().mockResolvedValue({ id: 'call-1' })
    } as unknown as ToolCallRepository;

    const mockLlm = new MockLlmProviderAdapter(async (messages) => {
      const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
      const userText = lastUserMsg?.content || '';
      const lastToolMsg = [...messages].reverse().find((m) => m.role === 'tool');

      if (lastToolMsg) {
        const res = JSON.parse(lastToolMsg.content);
        if (lastToolMsg.name === 'quote') {
          if (res.error) {
            return {
              text: 'Não temos esse produto no nosso catálogo.',
              toolCalls: [],
              finishReason: 'STOP',
              usage: { inputTokens: 20, outputTokens: 10 }
            };
          }
          const item = res.lineItems[0];
          return {
            text: `O produto ${item.name} (SKU: ${item.sku}) custa ${res.formattedTotal}.`,
            toolCalls: [],
            finishReason: 'STOP',
            usage: { inputTokens: 20, outputTokens: 10 }
          };
        }
        if (lastToolMsg.name === 'search_catalog') {
          const item = res.items[0];
          if (item && !item.available) {
            return {
              text: `O artigo ${item.name} encontra-se de momento esgotado e indisponível para entrega.`,
              toolCalls: [],
              finishReason: 'STOP',
              usage: { inputTokens: 20, outputTokens: 10 }
            };
          }
        }
      }

      if (userText.includes('CAM-01')) {
        return {
          text: '',
          toolCalls: [{ id: 'call_1', name: 'quote', arguments: { skus: ['CAM-01'] } }],
          finishReason: 'TOOL_CALL',
          usage: { inputTokens: 20, outputTokens: 10 }
        };
      }
      if (userText.includes('CAL-02')) {
        return {
          text: '',
          toolCalls: [{ id: 'call_2', name: 'quote', arguments: { skus: ['CAL-02'] } }],
          finishReason: 'TOOL_CALL',
          usage: { inputTokens: 20, outputTokens: 10 }
        };
      }
      if (userText.includes('Sapatos Couro')) {
        return {
          text: '',
          toolCalls: [{ id: 'call_3', name: 'search_catalog', arguments: { query: 'Sapatos Couro' } }],
          finishReason: 'TOOL_CALL',
          usage: { inputTokens: 20, outputTokens: 10 }
        };
      }

      // Non existent SKU probe
      return {
        text: '',
        toolCalls: [{ id: 'call_fake', name: 'quote', arguments: { skus: ['FAKE_SKU'] } }],
        finishReason: 'TOOL_CALL',
        usage: { inputTokens: 20, outputTokens: 10 }
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

    const smokeRunner = new CatalogSmokeRunner({
      executor,
      tenantId
    });

    const smokeResult = await smokeRunner.runSmokeEvals(sampleCatalog);

    expect(smokeResult.ok).toBe(true);
    expect(smokeResult.failed).toBe(0);
    expect(smokeResult.passed).toBe(4);
  });
});
