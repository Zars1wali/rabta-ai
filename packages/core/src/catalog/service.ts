import type {
  CatalogSource,
  VerifyResult
} from '@salesops/types';
import type { CatalogRepository, TenantRepository } from '../db/repositories.js';
import type { CatalogItemWithStaleness, StalenessEvaluation } from './types.js';
import { evaluateStaleness } from './staleness.js';

export class CatalogService {
  constructor(
    private catalogRepo: CatalogRepository,
    private tenantRepo: TenantRepository
  ) {}

  async syncCatalog(
    tenantId: string,
    source: CatalogSource,
    sourceConfig: unknown
  ): Promise<VerifyResult & { snapshotId?: string }> {
    // 1. Verify before saving
    const verifyResult = await source.verify(sourceConfig);
    if (!verifyResult.ok) {
      return verifyResult;
    }

    // 2. Fetch full catalog from source
    const catalog = await source.fetch(sourceConfig);

    // 3. Persist as append-only snapshot
    const snapshot = await this.catalogRepo.saveSnapshot(tenantId, catalog);

    return {
      ok: true,
      itemCount: catalog.items.length,
      sample: catalog.items.slice(0, 5),
      warnings: verifyResult.warnings,
      snapshotId: snapshot.id
    };
  }

  async search(
    tenantId: string,
    options: {
      query?: string;
      category?: string;
      maxPriceMinor?: number;
      limit?: number;
    } = {}
  ): Promise<{ items: CatalogItemWithStaleness[]; staleness: StalenessEvaluation }> {
    const activeData = await this.catalogRepo.getActiveSnapshot(tenantId);
    if (!activeData) {
      return {
        items: [],
        staleness: {
          state: 'stale',
          ageMinutes: Infinity,
          maxAgeMinutes: 240,
          action: 'refuse',
          disclaimer: 'No active catalog snapshot found.'
        }
      };
    }

    const tenant = await this.tenantRepo.getById(tenantId);
    const stalenessConfig = tenant?.config.catalog.staleness ?? {
      maxAgeMinutes: 240,
      onStale: 'hedge_price' as const
    };

    const staleness = evaluateStaleness(
      activeData.snapshot.fetchedAt,
      stalenessConfig.maxAgeMinutes,
      stalenessConfig.onStale
    );

    if (staleness.action === 'refuse') {
      return {
        items: [],
        staleness
      };
    }

    const rawItems = await this.catalogRepo.searchItems(tenantId, options);
    const items: CatalogItemWithStaleness[] = rawItems.map((item) => ({
      ...item,
      isStale: staleness.state === 'stale',
      stalenessDisclaimer: staleness.disclaimer
    }));

    return {
      items,
      staleness
    };
  }

  async getBySku(
    tenantId: string,
    sku: string
  ): Promise<{ item: CatalogItemWithStaleness | null; staleness: StalenessEvaluation }> {
    const activeData = await this.catalogRepo.getActiveSnapshot(tenantId);
    if (!activeData) {
      return {
        item: null,
        staleness: {
          state: 'stale',
          ageMinutes: Infinity,
          maxAgeMinutes: 240,
          action: 'refuse',
          disclaimer: 'No active catalog snapshot found.'
        }
      };
    }

    const tenant = await this.tenantRepo.getById(tenantId);
    const stalenessConfig = tenant?.config.catalog.staleness ?? {
      maxAgeMinutes: 240,
      onStale: 'hedge_price' as const
    };

    const staleness = evaluateStaleness(
      activeData.snapshot.fetchedAt,
      stalenessConfig.maxAgeMinutes,
      stalenessConfig.onStale
    );

    if (staleness.action === 'refuse') {
      return {
        item: null,
        staleness
      };
    }

    const rawItem = await this.catalogRepo.getItemBySku(tenantId, sku);
    const item: CatalogItemWithStaleness | null = rawItem
      ? {
          ...rawItem,
          isStale: staleness.state === 'stale',
          stalenessDisclaimer: staleness.disclaimer
        }
      : null;

    return {
      item,
      staleness
    };
  }
}
