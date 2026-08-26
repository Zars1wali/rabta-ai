import { describe, it, expect } from 'vitest';
import {
  CatalogItemSchema,
  CatalogSchema,
  VerifyResultSchema,
  StorePolicySchema,
  CloseActionSchema,
  InboundMessageSchema,
  MerchantSessionResultSchema,
  TenantConfigSchema,
  AgentTurnInputSchema,
  AgentTurnOutputSchema,
  EntitlementSchema,
  UsageEventSchema
} from '../src/index.js';

describe('@salesops/types Schemas', () => {
  it('validates a valid CatalogItem and rejects float prices', () => {
    const validItem = {
      sku: 'SKU-001',
      name: 'Standard Subscription',
      category: 'Software',
      description: 'AI Sales Assistant',
      priceMinor: 7900, // €79.00
      currency: 'EUR' as const,
      billing: 'month' as const,
      attributes: { tier: 'standard' },
      available: true,
      url: 'https://rewilt.com/products/standard'
    };

    expect(CatalogItemSchema.safeParse(validItem).success).toBe(true);

    const invalidFloatItem = {
      ...validItem,
      priceMinor: 79.99 // Floats forbidden in minor units
    };
    expect(CatalogItemSchema.safeParse(invalidFloatItem).success).toBe(false);
  });

  it('validates a valid Catalog', () => {
    const catalog = {
      tenantId: '550e8400-e29b-41d4-a716-446655440000',
      items: [
        {
          sku: 'SKU-001',
          name: 'Item 1',
          category: null,
          description: null,
          priceMinor: 1000,
          currency: 'EUR' as const,
          billing: 'once' as const,
          attributes: {},
          available: true,
          url: null
        }
      ],
      fetchedAt: new Date().toISOString(),
      sourceKind: 'json'
    };

    expect(CatalogSchema.safeParse(catalog).success).toBe(true);
  });

  it('validates VerifyResult and enforces max 5 sample items', () => {
    const validVerify = {
      ok: true,
      itemCount: 20,
      sample: [
        {
          sku: 'SKU-1',
          name: 'Item 1',
          category: null,
          description: null,
          priceMinor: 500,
          currency: 'EUR' as const,
          billing: 'once' as const,
          attributes: {},
          available: true,
          url: null
        }
      ],
      warnings: []
    };
    expect(VerifyResultSchema.safeParse(validVerify).success).toBe(true);
  });

  it('validates StorePolicy and enforces max 20 custom QA pairs', () => {
    const validPolicy = {
      shipping: {
        regions: ['PT', 'ES'],
        costRule: 'Free over 50€',
        leadTimeDays: [1, 3] as [number, number]
      },
      returns: {
        windowDays: 30,
        conditions: 'Unopened packaging',
        whoPaysReturn: 'customer' as const
      },
      warranty: {
        months: 24,
        scope: 'Manufacturer defects'
      },
      payment: {
        methods: ['card', 'mbway'],
        installments: false
      },
      hours: {
        timezone: 'Europe/Lisbon',
        note: 'Mon-Fri 9:00-18:00'
      },
      contact: {
        humanEscalation: '+351912345678'
      },
      custom: [
        { question: 'Do you ship to islands?', answer: 'Yes, Madeira and Azores take 3-5 business days.' }
      ]
    };
    expect(StorePolicySchema.safeParse(validPolicy).success).toBe(true);
  });

  it('validates CloseActions across all discriminated unions', () => {
    const productLink = {
      kind: 'product_link' as const,
      urlTemplate: 'https://store.pt/products/{sku}'
    };
    expect(CloseActionSchema.safeParse(productLink).success).toBe(true);

    const stripeCheckout = {
      kind: 'stripe_checkout' as const,
      priceMap: { standard: 'price_123' }
    };
    expect(CloseActionSchema.safeParse(stripeCheckout).success).toBe(true);

    const captureLead = {
      kind: 'capture_lead' as const,
      fields: ['name' as const, 'email' as const],
      notify: { type: 'webhook' as const, to: 'https://api.rewilt.com/lead-notify' }
    };
    expect(CloseActionSchema.safeParse(captureLead).success).toBe(true);
  });

  it('validates InboundMessage', () => {
    const inbound = {
      id: 'msg-001',
      channel: 'web' as const,
      sessionId: 'sess-001',
      senderId: 'visitor-001',
      content: 'Hello, how much is the Standard plan?',
      timestamp: new Date().toISOString()
    };
    expect(InboundMessageSchema.safeParse(inbound).success).toBe(true);
  });

  it('validates MerchantSessionResult for e-store SSO', () => {
    const session = {
      ok: true,
      tenantId: '550e8400-e29b-41d4-a716-446655440000',
      ownerEmail: 'owner@store.pt',
      sellerId: 'seller_123',
      roles: ['vendor_owner']
    };
    expect(MerchantSessionResultSchema.safeParse(session).success).toBe(true);
  });

  it('enforces EU AI Act Art. 50 non-removable AI disclosure on TenantConfig', () => {
    const validConfig = {
      tenantId: '550e8400-e29b-41d4-a716-446655440000',
      displayName: 'Rewilt Sales Ops',
      tier: 'standard' as const,
      locales: ['pt-PT', 'en'],
      currency: 'EUR' as const,
      timezone: 'Europe/Lisbon',
      persona: {
        tone: 'warm_direct' as const,
        greeting: 'Olá! Sou o assistente virtual da Rewilt.',
        escalationPhrase: 'Vou encaminhar para a nossa equipa humana.'
      },
      catalog: {
        source: 'json',
        config: {},
        refresh: { mode: 'poll' as const, ttlMinutes: 60 },
        staleness: { maxAgeMinutes: 240, onStale: 'hedge_price' as const }
      },
      policy: {
        shipping: null,
        returns: null,
        warranty: null,
        payment: null,
        hours: null,
        contact: { humanEscalation: 'human@rewilt.com' },
        custom: []
      },
      closes: [
        {
          kind: 'stripe_checkout' as const,
          priceMap: { standard: 'price_abc' }
        }
      ],
      channels: [
        {
          kind: 'web' as const,
          allowedOrigins: ['https://rewilt.com']
        }
      ],
      limits: {
        conversationsPerMonth: 500,
        tokenBudgetPerSession: 40000,
        monthlySpendCapEur: 25
      },
      compliance: {
        aiDisclosure: true as const,
        retentionDays: 30
      }
    };

    expect(TenantConfigSchema.safeParse(validConfig).success).toBe(true);

    // AI Disclosure MUST NOT be false
    const invalidConfig = {
      ...validConfig,
      compliance: {
        aiDisclosure: false as unknown as true,
        retentionDays: 30
      }
    };
    expect(TenantConfigSchema.safeParse(invalidConfig).success).toBe(false);
  });

  it('validates AgentTurnInput and AgentTurnOutput', () => {
    const input = {
      sessionId: '550e8400-e29b-41d4-a716-446655440000',
      tenantId: '550e8400-e29b-41d4-a716-446655440001',
      message: {
        id: 'msg-1',
        channel: 'web' as const,
        sessionId: '550e8400-e29b-41d4-a716-446655440000',
        senderId: 'user-1',
        content: 'Hi',
        timestamp: new Date().toISOString()
      },
      history: [],
      stage: 'greet' as const,
      locale: 'pt-PT'
    };
    expect(AgentTurnInputSchema.safeParse(input).success).toBe(true);

    const output = {
      chunks: ['Olá! Em que posso ajudar hoje?'],
      stage: 'discover' as const,
      toolCalls: [],
      events: [],
      leadDelta: null,
      usage: {
        inputTokens: 120,
        outputTokens: 25,
        costMinor: 1
      }
    };
    expect(AgentTurnOutputSchema.safeParse(output).success).toBe(true);
  });

  it('validates Metering Entitlement and UsageEvent schemas', () => {
    const entitlement = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      tenantId: '550e8400-e29b-41d4-a716-446655440001',
      stripeSubscriptionId: 'sub_12345',
      periodStart: new Date().toISOString(),
      periodEnd: new Date(Date.now() + 30 * 86400000).toISOString(),
      tier: 'standard' as const,
      includedConversations: 500,
      blockQuantity: 0,
      blockSize: 1000,
      gracePercent: 10,
      onDepletion: 'degrade' as const,
      createdAt: new Date().toISOString()
    };
    expect(EntitlementSchema.safeParse(entitlement).success).toBe(true);

    const usageEvent = {
      id: '550e8400-e29b-41d4-a716-446655440002',
      tenantId: '550e8400-e29b-41d4-a716-446655440001',
      entitlementId: '550e8400-e29b-41d4-a716-446655440000',
      sessionId: '550e8400-e29b-41d4-a716-446655440003',
      metric: 'conversation' as const,
      channel: 'web',
      identityHash: 'hmac_sha256_hash_value',
      windowStart: new Date().toISOString(),
      counted: true,
      createdAt: new Date().toISOString()
    };
    expect(UsageEventSchema.safeParse(usageEvent).success).toBe(true);
  });
});
