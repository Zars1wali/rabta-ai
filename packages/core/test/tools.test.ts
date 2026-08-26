import { describe, it, expect, vi } from 'vitest';
import {
  defaultToolRegistry,
  DEFAULT_TOOL_DECLARATIONS,
  searchCatalogTool,
  quoteTool,
  getPolicyTool,
  createSubscriptionCheckoutTool,
  createPreviewCheckoutTool,
  captureLeadTool,
  requestHumanTool,
  type ToolExecutionContext
} from '../src/agent/tools/index.js';
import type { CatalogService } from '../src/catalog/service.js';
import type {
  SessionRepository,
  LeadRepository,
  TenantRepository,
  ToolCallRepository
} from '../src/db/repositories.js';
import { REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '../src/db/seed.js';

describe('Server-Resolved Agent Tools (WP-08)', () => {
  const tenantId = REWILT_TENANT_ID;
  const sessionId = '00000000-0000-4000-8000-000000000099';

  const mockItem = {
    sku: 'salesops_standard',
    name: 'Sales Ops Standard',
    category: 'Planos',
    description: 'Plano padrão com 500 conversas',
    priceMinor: 7900,
    currency: 'EUR' as const,
    billing: 'month' as const,
    available: true,
    url: 'https://rewilt.com/pricing#standard',
    isStale: false,
    stalenessDisclaimer: null
  };

  const createMockContext = (overrides?: Partial<ToolExecutionContext>): ToolExecutionContext => {
    return {
      tenantId,
      sessionId,
      catalogService: {
        search: vi.fn().mockResolvedValue({
          items: [mockItem],
          staleness: { state: 'fresh' }
        }),
        getBySku: vi.fn().mockImplementation(async (_tId: string, sku: string) => {
          if (sku === 'salesops_standard') {
            return { item: mockItem, staleness: { state: 'fresh' } };
          }
          return { item: null, staleness: { state: 'fresh' } };
        })
      } as unknown as CatalogService,
      sessionRepo: {
        getSession: vi.fn().mockResolvedValue({
          id: sessionId,
          tenantId,
          consentAt: new Date()
        }),
        updateTurn: vi.fn().mockResolvedValue({ id: sessionId })
      } as unknown as SessionRepository,
      leadRepo: {
        createLead: vi.fn().mockResolvedValue({
          id: 'lead-123',
          tenantId,
          sessionId,
          name: 'João Silva',
          email: 'joao@loja.pt',
          createdAt: new Date().toISOString()
        })
      } as unknown as LeadRepository,
      tenantRepo: {
        getById: vi.fn().mockResolvedValue({
          id: tenantId,
          displayName: 'Rewilt Sales Ops',
          config: REWILT_TENANT_CONFIG
        })
      } as unknown as TenantRepository,
      toolCallRepo: {
        recordToolCall: vi.fn().mockResolvedValue({ id: 'tool-call-1' })
      } as unknown as ToolCallRepository,
      ...overrides
    };
  };

  it('declares all 7 tools in DEFAULT_TOOL_DECLARATIONS with strict schemas', () => {
    expect(DEFAULT_TOOL_DECLARATIONS.length).toBe(7);
    const names = DEFAULT_TOOL_DECLARATIONS.map((d) => d.name);
    expect(names).toEqual([
      'search_catalog',
      'quote',
      'get_policy',
      'create_subscription_checkout',
      'create_preview_checkout',
      'capture_lead',
      'request_human'
    ]);
  });

  describe('1. search_catalog', () => {
    it('executes search and returns structured items and staleness', async () => {
      const ctx = createMockContext();
      const output = await searchCatalogTool.execute({ query: 'Standard', limit: 5 }, ctx);

      expect(output.ok).toBe(true);
      expect((output.result.items as unknown[]).length).toBe(1);
      expect(output.result.stalenessState).toBe('fresh');
      expect(ctx.catalogService.search).toHaveBeenCalledWith(
        tenantId,
        expect.objectContaining({ query: 'Standard', limit: 5 })
      );
    });
  });

  describe('2. quote', () => {
    it('computes exact server-side pricing totals from priceMinor', async () => {
      const ctx = createMockContext();
      const output = await quoteTool.execute(
        { skus: ['salesops_standard'], quantity: 2, term: 'month' },
        ctx
      );

      expect(output.ok).toBe(true);
      // 7900 * 2 = 15800 minor units = 158.00 EUR
      expect(output.result.totalMinor).toBe(15800);
      expect(output.result.formattedTotal).toBe('158.00 EUR');
      const items = output.result.lineItems as Array<{ quantity: number }>;
      expect(items[0]?.quantity).toBe(2);
    });

    it('returns error when SKU is not found in catalog', async () => {
      const ctx = createMockContext();
      const output = await quoteTool.execute({ skus: ['unknown_sku'], quantity: 1, term: 'month' }, ctx);

      expect(output.ok).toBe(false);
      expect(output.result.error).toContain('not found in active catalog');
    });
  });

  describe('3. get_policy', () => {
    it('retrieves store policy sections from verified TenantConfig', async () => {
      const ctx = createMockContext();
      const output = await getPolicyTool.execute({ topic: 'returns' }, ctx);

      expect(output.ok).toBe(true);
      expect(output.result.topic).toBe('returns');
      const policyData = output.result.policy as { windowDays?: number };
      expect(policyData?.windowDays).toBe(14);
    });
  });

  describe('4. create_subscription_checkout', () => {
    it('generates Stripe checkout URL and emits checkout_url event', async () => {
      const ctx = createMockContext();
      const output = await createSubscriptionCheckoutTool.execute(
        { sku: 'salesops_standard', email: 'merchant@store.pt', locale: 'pt-PT' },
        ctx
      );

      expect(output.ok).toBe(true);
      expect(output.result.checkoutUrl).toContain('checkout.stripe.com');
      expect(output.event).toEqual({
        type: 'checkout_url',
        url: output.result.checkoutUrl
      });
    });
  });

  describe('5. create_preview_checkout', () => {
    it('generates 50 EUR preview checkout and emits checkout_url event', async () => {
      const ctx = createMockContext();
      const output = await createPreviewCheckoutTool.execute(
        { email: 'merchant@store.pt', shopUrl: 'https://minhaloja.pt', locale: 'pt-PT' },
        ctx
      );

      expect(output.ok).toBe(true);
      expect(output.result.priceMinor).toBe(5000);
      expect(output.result.creditedOnConversion).toBe(true);
      expect(output.event?.type).toBe('checkout_url');
    });
  });

  describe('6. capture_lead (Consent Enforced)', () => {
    it('strictly REJECTS lead capture if session lacks visitor consent (consent_at is null)', async () => {
      const ctx = createMockContext({
        sessionRepo: {
          getSession: vi.fn().mockResolvedValue({
            id: sessionId,
            tenantId,
            consentAt: null // NO CONSENT
          })
        } as unknown as SessionRepository
      });

      const output = await captureLeadTool.execute(
        { name: 'Maria', email: 'maria@loja.pt', phone: '912345678' },
        ctx
      );

      expect(output.ok).toBe(false);
      expect(output.result.consentRequired).toBe(true);
      expect(output.result.error).toContain('explicit visitor consent (consent_at) is required');
      expect(ctx.leadRepo.createLead).not.toHaveBeenCalled();
    });

    it('successfully persists lead when consent_at is present on the session', async () => {
      const ctx = createMockContext();
      const output = await captureLeadTool.execute(
        { name: 'João Silva', email: 'joao@loja.pt', phone: '912345678' },
        ctx
      );

      expect(output.ok).toBe(true);
      expect(output.result.status).toBe('recorded');
      expect(output.result.leadId).toBe('lead-123');
      expect(output.event).toEqual({
        type: 'lead_captured',
        leadId: 'lead-123'
      });
      expect(ctx.leadRepo.createLead).toHaveBeenCalled();
    });
  });

  describe('7. request_human', () => {
    it('transitions stage to handoff and emits handoff event', async () => {
      const ctx = createMockContext();
      const output = await requestHumanTool.execute({ reason: 'Dúvida técnica sobre ERP customizado' }, ctx);

      expect(output.ok).toBe(true);
      expect(output.result.status).toBe('escalated');
      expect(output.result.stage).toBe('handoff');
      expect(output.event).toEqual({
        type: 'handoff_requested',
        target: {
          type: 'email',
          to: 'comercial@rewilt.com'
        }
      });
      expect(ctx.sessionRepo.updateTurn).toHaveBeenCalledWith(
        tenantId,
        sessionId,
        expect.objectContaining({ stage: 'handoff' })
      );
    });
  });

  describe('ToolRegistry Execution & Validation', () => {
    it('returns error on unknown tool names', async () => {
      const ctx = createMockContext();
      const res = await defaultToolRegistry.execute(
        { id: 'call_1', name: 'hack_database', arguments: {} },
        ctx
      );

      expect(res.ok).toBe(false);
      expect(res.result.error).toContain('not recognized');
    });

    it('returns validation error on malformed tool arguments', async () => {
      const ctx = createMockContext();
      // quote requires skus to be a non-empty array
      const res = await defaultToolRegistry.execute(
        { id: 'call_2', name: 'quote', arguments: { skus: [] } },
        ctx
      );

      expect(res.ok).toBe(false);
      expect(res.result.error).toContain('Invalid tool arguments');
    });
  });
});
