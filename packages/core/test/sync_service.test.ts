import { describe, it, expect, vi } from 'vitest';
import { CatalogSyncService } from '../src/catalog/sync_service.js';
import type { CatalogRepository, EvalRunRepository } from '../src/db/repositories.js';
import type { Catalog, CatalogSource } from '@salesops/types';
import { REWILT_TENANT_ID } from '../src/db/seed.js';

describe('CatalogSyncService & Smoke Gate (WP-16)', () => {
  const tenantId = REWILT_TENANT_ID;

  const mockCatalog: Catalog = {
    tenantId,
    sourceKind: 'csv',
    fetchedAt: new Date().toISOString(),
    items: [
      {
        sku: 'SKU-01',
        name: 'Item Teste',
        category: 'Geral',
        description: 'Descrição',
        priceMinor: 5000,
        currency: 'EUR',
        billing: 'month',
        available: true,
        attributes: {},
        url: null
      }
    ]
  };

  const mockSource: CatalogSource = {
    kind: 'csv',
    supportsWebhooks: () => false,
    verify: vi.fn(),
    fetch: vi.fn().mockResolvedValue(mockCatalog)
  };

  it('syncs and activates new snapshot when smoke evaluation passes', async () => {
    const mockCatalogRepo = {
      saveSnapshot: vi.fn().mockResolvedValue({
        id: 'snapshot-new-123',
        tenantId,
        sourceKind: 'csv',
        fetchedAt: new Date(),
        itemCount: 1,
        status: 'active'
      })
    } as unknown as CatalogRepository;

    const mockEvalRepo = {
      recordRun: vi.fn().mockResolvedValue({ id: 'eval-run-1' })
    } as unknown as EvalRunRepository;

    const mockSmokeEvaluator = {
      runSmokeEvals: vi.fn().mockResolvedValue({
        ok: true,
        total: 4,
        passed: 4,
        failed: 0,
        suiteResult: { suite: 'catalog_smoke', passed: 4, failed: 0 }
      })
    };

    const syncService = new CatalogSyncService(mockCatalogRepo, mockEvalRepo);

    const result = await syncService.syncAndActivate({
      tenantId,
      source: mockSource,
      sourceConfig: { filePath: 'test.csv' },
      smokeEvaluator: mockSmokeEvaluator
    });

    expect(result.success).toBe(true);
    expect(result.snapshotId).toBe('snapshot-new-123');
    expect(result.smokePassed).toBe(true);
    expect(mockCatalogRepo.saveSnapshot).toHaveBeenCalledWith(tenantId, mockCatalog);
    expect(mockEvalRepo.recordRun).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantId,
        suite: 'catalog_smoke',
        passed: 4,
        failed: 0
      })
    );
  });

  it('blocks snapshot activation when smoke evaluation fails', async () => {
    const mockCatalogRepo = {
      saveSnapshot: vi.fn()
    } as unknown as CatalogRepository;

    const mockEvalRepo = {
      recordRun: vi.fn().mockResolvedValue({ id: 'eval-run-2' })
    } as unknown as EvalRunRepository;

    const mockSmokeEvaluator = {
      runSmokeEvals: vi.fn().mockResolvedValue({
        ok: false,
        total: 4,
        passed: 2,
        failed: 2, // FAILED
        suiteResult: { suite: 'catalog_smoke', passed: 2, failed: 2 }
      })
    };

    const syncService = new CatalogSyncService(mockCatalogRepo, mockEvalRepo);

    const result = await syncService.syncAndActivate({
      tenantId,
      source: mockSource,
      sourceConfig: { filePath: 'test.csv' },
      smokeEvaluator: mockSmokeEvaluator
    });

    // Asserts gate blocked activation
    expect(result.success).toBe(false);
    expect(result.smokePassed).toBe(false);
    expect(result.error).toContain('Catalog snapshot activation blocked: Smoke eval suite failed');

    // Asserts no snapshot was created
    expect(mockCatalogRepo.saveSnapshot).not.toHaveBeenCalled();

    // Asserts failure was logged in eval_runs table
    expect(mockEvalRepo.recordRun).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantId,
        passed: 2,
        failed: 2
      })
    );
  });
});
