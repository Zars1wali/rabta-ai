import type { TenantConfig, Catalog } from '@salesops/types';
import { TenantRepository, CatalogRepository } from './repositories.js';
import type { Database } from './client.js';

export const REWILT_TENANT_ID = '00000000-0000-4000-8000-000000000001';

export const REWILT_TENANT_CONFIG: TenantConfig = {
  version: 1,
  tenantId: REWILT_TENANT_ID,
  displayName: 'Rewilt Sales Ops',
  tier: 'standard',
  locales: ['pt-PT', 'es-ES', 'en'],
  currency: 'EUR',
  timezone: 'Europe/Lisbon',

  persona: {
    tone: 'warm_direct',
    greeting:
      'Olá! Sou o assistente de vendas da Rewilt. Ajudo lojas e empresas a qualificarem clientes, responderem a dúvidas e fecharem vendas automaticamente.',
    escalationPhrase:
      'Compreendo a sua questão específica. Vou encaminhar este contacto para um dos nossos especialistas humanos.'
  },

  catalog: {
    source: 'json',
    config: { path: 'rewilt-packages.json' },
    refresh: { mode: 'poll', ttlMinutes: 60 },
    staleness: { maxAgeMinutes: 240, onStale: 'hedge_price' }
  },

  policy: {
    shipping: null,
    returns: {
      windowDays: 14,
      conditions: 'Reembolso integral caso o setup inicial ou teste não correspondam ao especificado.',
      whoPaysReturn: 'store'
    },
    warranty: {
      months: 12,
      scope: 'SLA de disponibilidade do agente de 99.5% e atualizações contínuas de conformidade com o EU AI Act.'
    },
    payment: {
      methods: ['Cartão de Crédito', 'Débito Direto SEPA', 'Stripe'],
      installments: false
    },
    hours: {
      timezone: 'Europe/Lisbon',
      note: 'Agente ativo 24/7. Suporte humano disponível de Segunda a Sexta das 9:00 às 18:00.'
    },
    contact: {
      humanEscalation: 'comercial@rewilt.com'
    },
    custom: [
      {
        question: 'O agente inventa respostas ou preços que não existem no meu catálogo?',
        answer:
          'Não. O agente utiliza ferramentas de consulta estritas do lado do servidor e tem regras rígidas de integridade. Nunca afirma um preço ou stock sem confirmação da base de dados.'
      },
      {
        question: 'O agente está em conformidade com o EU AI Act?',
        answer:
          'Sim. Cumpre integralmente o Artigo 50 do Regulamento Europeu de IA, identificando-se imediatamente como inteligência artificial na primeira mensagem.'
      },
      {
        question: 'Como funciona a pré-visualização de 50€?',
        answer:
          'Construímos uma demonstração funcional com o seu próprio catálogo de produtos. Se subscrever um plano, os 50€ são creditados na sua primeira mensalidade.'
      }
    ]
  },

  closes: [
    {
      kind: 'stripe_checkout',
      priceMap: {
        lite_monthly: 'salesops_lite_monthly_eur',
        standard_monthly: 'salesops_standard_monthly_eur',
        europe_monthly: 'salesops_europe_monthly_eur',
        premium_monthly: 'salesops_premium_monthly_eur',
        preview: 'salesops_preview_eur'
      }
    },
    {
      kind: 'capture_lead',
      fields: ['name', 'email', 'phone', 'company_url', 'notes'],
      notify: { type: 'webhook', to: 'https://api.rewilt.com/api/salesops/leads/notify' }
    }
  ],

  channels: [
    {
      kind: 'web',
      allowedOrigins: ['https://rewilt.com', 'https://staging.rewilt.com', 'http://localhost:3000']
    }
  ],

  limits: {
    conversationsPerMonth: 500,
    tokenBudgetPerSession: 40000,
    monthlySpendCapEur: 25
  },

  compliance: {
    aiDisclosure: true,
    retentionDays: 30,
    dpaAcceptedAt: '2026-08-26T00:00:00.000Z'
  }
};

export const REWILT_CATALOG: Catalog = {
  tenantId: REWILT_TENANT_ID,
  fetchedAt: new Date().toISOString(),
  sourceKind: 'json',
  items: [
    {
      sku: 'salesops_lite',
      name: 'Sales Ops Lite',
      category: 'Planos',
      description:
        'Agente conversacional de entrada para pequenos catálogos. 300 conversas/mês, widget web, 2 idiomas, modelo Gemini Flash-Lite.',
      priceMinor: 2900,
      currency: 'EUR',
      billing: 'month',
      attributes: {
        conversationsIncluded: 300,
        channels: 'web',
        voiceEnabled: false
      },
      available: true,
      url: 'https://rewilt.com/pricing#lite'
    },
    {
      sku: 'salesops_standard',
      name: 'Sales Ops Standard',
      category: 'Planos',
      description:
        'O plano padrão para comércio online. 500 conversas/mês, canais Web e WhatsApp, suporte a notas de voz e visão, escalamento automático de modelo.',
      priceMinor: 7900,
      currency: 'EUR',
      billing: 'month',
      attributes: {
        conversationsIncluded: 500,
        channels: 'web,whatsapp',
        voiceEnabled: true
      },
      available: true,
      url: 'https://rewilt.com/pricing#standard'
    },
    {
      sku: 'salesops_europe',
      name: 'Sales Ops Europe',
      category: 'Planos',
      description:
        'Residência de dados integral na União Europeia. Endpoints e processamento exclusivamente na UE (Mistral / Vertex EU), pacote DPA Artigo 28 do RGPD.',
      priceMinor: 9900,
      currency: 'EUR',
      billing: 'month',
      attributes: {
        conversationsIncluded: 500,
        channels: 'web,whatsapp',
        dataResidency: 'EU'
      },
      available: true,
      url: 'https://rewilt.com/pricing#europe'
    },
    {
      sku: 'salesops_premium',
      name: 'Sales Ops Premium',
      category: 'Planos',
      description:
        'Para catálogos extensos e vendas B2B de alto valor. Modelos frontier, suporte multi-número WhatsApp e suporte prioritário dedicado.',
      priceMinor: 19900,
      currency: 'EUR',
      billing: 'month',
      attributes: {
        conversationsIncluded: 500,
        channels: 'web,whatsapp_multi',
        prioritySupport: true
      },
      available: true,
      url: 'https://rewilt.com/pricing#premium'
    },
    {
      sku: 'salesops_preview',
      name: 'Demonstração Personalizada de Loja (€50)',
      category: 'Serviços',
      description:
        'Criamos um agente de teste funcional com até 100 produtos do seu catálogo real. Os 50€ são 100% creditados na subscrição do seu primeiro mês.',
      priceMinor: 5000,
      currency: 'EUR',
      billing: 'once',
      attributes: {
        creditedOnConversion: true
      },
      available: true,
      url: 'https://rewilt.com/preview'
    }
  ]
};

export const ZPI_TENANT_ID = '00000000-0000-4000-8000-000000000002';

export const ZPI_TENANT_CONFIG: TenantConfig = {
  version: 1,
  tenantId: ZPI_TENANT_ID,
  displayName: 'ZeroPointIntel Cybersecurity & AI Ops',
  tier: 'europe',
  locales: ['en', 'pt-PT'],
  currency: 'EUR',
  timezone: 'Europe/Lisbon',

  persona: {
    tone: 'professional_technical',
    greeting:
      'Welcome to ZeroPointIntel. We deliver high-assurance autonomous agent security, EU AI Act compliance, and AI Ops architecture.',
    escalationPhrase:
      'I will connect you directly with a ZeroPointIntel principal security engineer.'
  },

  catalog: {
    source: 'json',
    config: { path: 'zpi-packages.json' },
    refresh: { mode: 'poll', ttlMinutes: 60 },
    staleness: { maxAgeMinutes: 240, onStale: 'hedge_price' }
  },

  policy: {
    shipping: null,
    returns: {
      windowDays: 30,
      conditions: 'Satisfaction guarantee on all architecture assessments and security audits.',
      whoPaysReturn: 'store'
    },
    warranty: {
      months: 24,
      scope: 'Continuous automated EU AI Act conformity monitoring and enterprise SLA.'
    },
    payment: {
      methods: ['Stripe', 'Bank Wire Transfer', 'Crypto USDC'],
      installments: false
    },
    hours: {
      timezone: 'Europe/Lisbon',
      note: '24/7 autonomous monitoring with global dedicated engineering response within 1 hour.'
    },
    contact: {
      humanEscalation: 'security@zeropointintel.com'
    },
    custom: [
      {
        question: 'What is the turnaround time for an EU AI Act Article 50 & 52 audit?',
        answer: 'Comprehensive assessment reports and technical documentation are delivered within 48 business hours.'
      }
    ]
  },

  closes: [
    {
      kind: 'stripe_checkout',
      priceMap: {
        ai_act_audit: 'zpi_ai_act_audit_eur',
        agent_soc_monthly: 'zpi_agent_soc_monthly_eur',
        salesops_preview: 'salesops_preview_eur',
        salesops_standard: 'salesops_standard_monthly_eur',
        salesops_europe: 'salesops_europe_monthly_eur'
      }
    },
    {
      kind: 'capture_lead',
      fields: ['name', 'email', 'phone', 'company_url', 'notes'],
      notify: { type: 'email', to: 'security@zeropointintel.com' }
    }
  ],

  channels: [
    {
      kind: 'web',
      allowedOrigins: ['https://zeropointintel.com', 'https://www.zeropointintel.com', 'http://localhost:3000']
    }
  ],

  limits: {
    conversationsPerMonth: 1000,
    tokenBudgetPerSession: 60000,
    monthlySpendCapEur: 100
  },

  compliance: {
    aiDisclosure: true,
    retentionDays: 90
  }
};

export const ZPI_CATALOG: Catalog = {
  tenantId: ZPI_TENANT_ID,
  sourceKind: 'json',
  fetchedAt: new Date().toISOString(),
  items: [
    {
      sku: 'salesops_preview',
      name: 'SalesOps 24h Store Preview Agent',
      category: 'AI Sales Agents',
      description:
        'A private live sales agent connected to your real WooCommerce, Shopify, or CSV catalog within 24 hours. 100% credited toward your first month subscription.',
      priceMinor: 5000, // €50.00
      currency: 'EUR',
      billing: 'once',
      attributes: {
        turnaround: '24 hours',
        creditGuarantee: '100% credited to first month'
      },
      available: true,
      url: 'https://zeropointintel.com/preview'
    },
    {
      sku: 'salesops_standard',
      name: 'SalesOps Standard AI Sales Employee (Monthly)',
      category: 'AI Sales Agents',
      description:
        '24/7 automated sales closing agent for your website with 500 included conversations, live stock checks, and direct Stripe checkout generation.',
      priceMinor: 7900, // €79.00 / month
      currency: 'EUR',
      billing: 'month',
      attributes: {
        conversationsIncluded: 500,
        channels: 'Web Widget'
      },
      available: true,
      url: 'https://zeropointintel.com/standard'
    },
    {
      sku: 'salesops_europe',
      name: 'SalesOps Europe & WhatsApp AI Sales Employee (Monthly)',
      category: 'AI Sales Agents',
      description:
        'Full omnichannel coverage on Web and Meta WhatsApp Business Cloud API with voice note transcription, human WhatsApp takeover (/pause), and 100% EU data residency.',
      priceMinor: 9900, // €99.00 / month
      currency: 'EUR',
      billing: 'month',
      attributes: {
        conversationsIncluded: 500,
        channels: 'Web Widget + Meta WhatsApp Cloud API',
        dataResidency: 'Paris/Frankfurt EU Datacenters'
      },
      available: true,
      url: 'https://zeropointintel.com/europe'
    },
    {
      sku: 'zpi_ai_act_audit',
      name: 'EU AI Act Article 50 & 52 Comprehensive Audit',
      category: 'Compliance & Safety',
      description:
        'End-to-end transparency, watermarking, risk classification, and technical documentation assessment with certified audit report.',
      priceMinor: 150000, // €1,500.00
      currency: 'EUR',
      billing: 'once',
      attributes: {
        slaHours: 48,
        deliverable: 'Certified PDF + remediation checklist'
      },
      available: true,
      url: 'https://zeropointintel.com/audit'
    },
    {
      sku: 'zpi_agent_soc_monthly',
      name: 'ZeroPoint Autonomous Agent SOC & Guardrails (Monthly)',
      category: 'Managed Security',
      description:
        'Continuous red-teaming, prompt injection monitoring, runtime budget guardrails, and real-time hallucination prevention.',
      priceMinor: 49000, // €490.00 / month
      currency: 'EUR',
      billing: 'month',
      attributes: {
        realTimeAlerts: true,
        guardrailLatencyMs: 15
      },
      available: true,
      url: 'https://zeropointintel.com/soc'
    }
  ]
};

export async function seedDatabase(db: Database) {
  const tenantRepo = new TenantRepository(db);
  const catalogRepo = new CatalogRepository(db);

  // 1. Upsert rewilt tenant
  const tenantRewilt = await tenantRepo.upsert({
    id: REWILT_TENANT_ID,
    slug: 'rewilt',
    displayName: REWILT_TENANT_CONFIG.displayName,
    config: REWILT_TENANT_CONFIG
  });

  // 2. Save rewilt catalog snapshot
  const snapshotRewilt = await catalogRepo.saveSnapshot(tenantRewilt.id, REWILT_CATALOG);

  // 3. Upsert ZeroPointIntel (ZPI) tenant (Zero new lines of application code!)
  const tenantZpi = await tenantRepo.upsert({
    id: ZPI_TENANT_ID,
    slug: 'zeropointintel',
    displayName: ZPI_TENANT_CONFIG.displayName,
    config: ZPI_TENANT_CONFIG
  });

  // 4. Save ZPI catalog snapshot
  const snapshotZpi = await catalogRepo.saveSnapshot(tenantZpi.id, ZPI_CATALOG);

  return {
    rewilt: { tenant: tenantRewilt, snapshot: snapshotRewilt },
    zpi: { tenant: tenantZpi, snapshot: snapshotZpi }
  };
}
