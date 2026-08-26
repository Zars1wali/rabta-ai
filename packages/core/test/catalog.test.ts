import { describe, it, expect, vi } from 'vitest';
import {
  evaluateStaleness,
  formatHedgedPriceStatement,
  CatalogService
} from '../src/catalog/index.js';
import type { CatalogRepository, TenantRepository } from '../src/db/repositories.js';
import type { Catalog, CatalogItem } from '@salesops/types';

describe('Catalog Staleness Engine', () => {
  it('correctly identifies fresh catalog snapshots', () => {
    const now = new Date('2026-08-26T12:00:00.000Z');
    const fetchedAt = new Date('2026-08-26T11:00:00.000Z'); // 60 minutes old

    const evaluation = evaluateStaleness(fetchedAt, 240, 'hedge_price', now);

    expect(evaluation.state).toBe('fresh');
    expect(evaluation.ageMinutes).toBe(60);
    expect(evaluation.maxAgeMinutes).toBe(240);
    expect(evaluation.action).toBe('none');
    expect(evaluation.disclaimer).toBeNull();
  });

  it('triggers hedge_price when snapshot exceeds maxAgeMinutes', () => {
    const now = new Date('2026-08-26T18:00:00.000Z');
    const fetchedAt = new Date('2026-08-26T12:00:00.000Z'); // 360 minutes old (limit 240)

    const evaluation = evaluateStaleness(fetchedAt, 240, 'hedge_price', now);

    expect(evaluation.state).toBe('stale');
    expect(evaluation.ageMinutes).toBe(360);
    expect(evaluation.action).toBe('hedge_price');
    expect(evaluation.disclaimer).toContain('checkout');
  });

  it('triggers refuse action when onStale is configured to refuse', () => {
    const now = new Date('2026-08-26T18:00:00.000Z');
    const fetchedAt = new Date('2026-08-26T12:00:00.000Z');

    const evaluation = evaluateStaleness(fetchedAt, 240, 'refuse', now);

    expect(evaluation.state).toBe('stale');
    expect(evaluation.action).toBe('refuse');
  });

  it('formats hedged price statements accurately across locales', () => {
    const ptStatement = formatHedgedPriceStatement(4900, 'EUR', 'pt-PT');
    expect(ptStatement).toContain('49,00');
    expect(ptStatement).toContain('checkout');

    const esStatement = formatHedgedPriceStatement(4900, 'EUR', 'es-ES');
    expect(esStatement).toContain('49,00');
    expect(esStatement).toContain('checkout');

    const enStatement = formatHedgedPriceStatement(4900, 'USD', 'en-US');
    expect(enStatement).toContain('49.00');
    expect(enStatement).toContain('checkout');
  });
});

describe('CatalogService', () => {
  const tenantId = '550e8400-e29b-41d4-a716-446655440000';

  const mockItem: CatalogItem = {
    sku: 'TEST-SKU',
    name: 'Test Item',
    category: 'Test Category',
    description: 'Test Description',
    priceMinor: 2500,
    currency: 'EUR',
    billing: 'month',
    attributes: {},
    available: true,
    url: 'https://store.pt/test'
  };

  it('searches items and attaches staleness flags when catalog is fresh', async () => {
    const mockCatalogRepo = {
      getActiveSnapshot: vi.fn().mockResolvedValue({
        snapshot: {
          id: 'snap-1',
          tenantId,
          fetchedAt: new Date(),
          itemCount: 1,
          status: 'active'
        },
        items: [mockItem]
      }),
      searchItems: vi.fn().mockResolvedValue([mockItem])
    } as unknown as CatalogRepository;

    const mockTenantRepo = {
      getById: vi.fn().mockResolvedValue({
        id: tenantId,
        config: {
          catalog: {
            staleness: { maxAgeMinutes: 240, onStale: 'hedge_price' }
          }
        }
      })
    } as unknown as TenantRepository;

    const service = new CatalogService(mockCatalogRepo, mockTenantRepo);
    const result = await service.search(tenantId, { query: 'Test' });

    expect(result.staleness.state).toBe('fresh');
    expect(result.items.length).toBe(1);
    expect(result.items[0]?.sku).toBe('TEST-SKU');
    expect(result.items[0]?.isStale).toBe(false);
  });

  it('retrieves item by SKU and marks isStale=true when stale', async () => {
    const staleDate = new Date(Date.now() - 500 * 60 * 1000); // 500 min ago

    const mockCatalogRepo = {
      getActiveSnapshot: vi.fn().mockResolvedValue({
        snapshot: {
          id: 'snap-1',
          tenantId,
          fetchedAt: staleDate,
          itemCount: 1,
          status: 'active'
        },
        items: [mockItem]
      }),
      getItemBySku: vi.fn().mockResolvedValue(mockItem)
    } as unknown as CatalogRepository;

    const mockTenantRepo = {
      getById: vi.fn().mockResolvedValue({
        id: tenantId,
        config: {
          catalog: {
            staleness: { maxAgeMinutes: 240, onStale: 'hedge_price' }
          }
        }
      })
    } as unknown as TenantRepository;

    const service = new CatalogService(mockCatalogRepo, mockTenantRepo);
    const result = await service.getBySku(tenantId, 'TEST-SKU');

    expect(result.staleness.state).toBe('stale');
    expect(result.item).not.toBeNull();
    expect(result.item?.sku).toBe('TEST-SKU');
    expect(result.item?.isStale).toBe(true);
    expect(result.item?.stalenessDisclaimer).toBeDefined();
  });

  it('syncs catalog using a verified CatalogSource adapter', async () => {
    const mockCatalogRepo = {
      saveSnapshot: vi.fn().mockResolvedValue({ id: 'snapshot-new-id' })
    } as unknown as CatalogRepository;
    const mockTenantRepo = {} as unknown as TenantRepository;

    const mockCatalog: Catalog = {
      tenantId,
      items: [mockItem],
      fetchedAt: new Date().toISOString(),
      sourceKind: 'json'
    };

    const mockSource = {
      kind: 'json',
      verify: vi.fn().mockResolvedValue({
        ok: true,
        itemCount: 1,
        sample: [mockItem],
        warnings: []
      }),
      fetch: vi.fn().mockResolvedValue(mockCatalog),
      supportsWebhooks: vi.fn().mockReturnValue(false)
    };

    const service = new CatalogService(mockCatalogRepo, mockTenantRepo);
    const syncResult = await service.syncCatalog(tenantId, mockSource, {});

    expect(syncResult.ok).toBe(true);
    expect(syncResult.itemCount).toBe(1);
    expect(syncResult.snapshotId).toBe('snapshot-new-id');
    expect(mockCatalogRepo.saveSnapshot).toHaveBeenCalledWith(tenantId, mockCatalog);
  });
});
