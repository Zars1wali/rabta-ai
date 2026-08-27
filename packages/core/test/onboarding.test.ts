import { describe, it, expect, vi } from 'vitest';
import { OnboardingService, type OnboardingDraft } from '../src/admin/index.js';
import type { TenantRepository, CatalogRepository } from '../src/db/repositories.js';

describe('Self-Service Onboarding Service (WP-17)', () => {
  const mockTenantRepo = {
    upsert: vi.fn().mockImplementation(async (data) => ({
      id: data.id,
      slug: data.slug,
      displayName: data.displayName,
      config: data.config,
      createdAt: new Date(),
      updatedAt: new Date()
    }))
  } as unknown as TenantRepository;

  const mockCatalogRepo = {
    saveSnapshot: vi.fn().mockImplementation(async (tenantId, catalog) => ({
      id: 'snap-created-999',
      tenantId,
      sourceKind: catalog.sourceKind,
      fetchedAt: new Date(),
      itemCount: catalog.items.length,
      status: 'active'
    }))
  } as unknown as CatalogRepository;

  const onboardingService = new OnboardingService(mockTenantRepo, mockCatalogRepo);

  it('verifies CSV source and returns 5 sample items', async () => {
    const csvContent = `SKU,Name,Price,Category,Description\nCAM-01,"Camisa Linho",45.00,Vestuário,"Camisa 100% linho"\nCAL-02,"Calça Sarja",55.00,Vestuário,"Calça confortável"`;
    const res = await onboardingService.verifySource('csv', {
      tenantId: '00000000-0000-4000-8000-000000000001',
      csvData: csvContent,
      defaultCurrency: 'EUR'
    });

    expect(res.ok).toBe(true);
    expect(res.itemCount).toBe(2);
    expect(res.sample.length).toBe(2);
    expect(res.sample[0]?.sku).toBe('CAM-01');
    expect(res.sample[0]?.priceMinor).toBe(4500);
  });

  it('provisions new merchant tenant and generates embed code', async () => {
    const csvContent = `SKU,Name,Price,Category,Description\nSKU-100,"Óculos de Sol",89.00,Acessórios,"Proteção UV 400"`;

    const draft: OnboardingDraft = {
      slug: 'otica-central',
      displayName: 'Ótica Central',
      tier: 'standard',
      locales: ['pt-PT'],
      currency: 'EUR',
      timezone: 'Europe/Lisbon',
      sourceKind: 'csv',
      sourceConfig: {
        csvData: csvContent,
        defaultCurrency: 'EUR'
      },
      policy: {
        shipping: null,
        returns: {
          windowDays: 14,
          conditions: 'Devoluções na embalagem original.',
          whoPaysReturn: 'store'
        },
        warranty: {
          months: 24,
          scope: 'Garantia de fabrico.'
        },
        payment: {
          methods: ['Stripe', 'Multibanco', 'MB WAY'],
          installments: false
        },
        hours: {
          timezone: 'Europe/Lisbon',
          note: 'Segunda a Sábado 9h-19h'
        },
        contact: {
          humanEscalation: 'geral@oticacentral.pt'
        },
        custom: []
      },
      closes: [
        {
          kind: 'capture_lead',
          fields: ['name', 'email', 'phone'],
          notify: { type: 'email', to: 'geral@oticacentral.pt' }
        }
      ],
      persona: {
        tone: 'warm_direct',
        greeting: 'Olá! Bem-vindo à Ótica Central. Como posso ajudar com os seus óculos?',
        escalationPhrase: 'Vou encaminhar para o nosso optometrista.'
      },
      allowedOrigins: ['https://oticacentral.pt']
    };

    const res = await onboardingService.provisionTenant(draft);

    expect(res.ok).toBe(true);
    expect(res.slug).toBe('otica-central');
    expect(res.tenantId).toBeDefined();
    expect(res.embedSnippet).toContain(`data-tenant-id="${res.tenantId}"`);
    expect(res.itemCount).toBe(1);
    expect(res.sample?.[0]?.sku).toBe('SKU-100');

    expect(mockTenantRepo.upsert).toHaveBeenCalledWith(
      expect.objectContaining({
        slug: 'otica-central',
        displayName: 'Ótica Central'
      })
    );
    expect(mockCatalogRepo.saveSnapshot).toHaveBeenCalled();
  });
});
