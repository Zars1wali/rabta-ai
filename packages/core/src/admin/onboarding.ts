import {
  type CatalogItem,
  type TenantConfig,
  type VerifyResult,
  TenantConfigSchema
} from '@salesops/types';
import type { TenantRepository, CatalogRepository } from '../db/repositories.js';
import { JsonCatalogSource } from '@salesops/adapter-catalog-json';
import { CsvCatalogSource } from '@salesops/adapter-catalog-csv';
import { WooCommerceCatalogSource } from '@salesops/adapter-catalog-woocommerce';

export interface OnboardingDraft {
  slug: string;
  displayName: string;
  tier?: 'lite' | 'standard' | 'europe' | 'premium' | 'custom';
  locales?: string[];
  currency?: 'EUR' | 'USD' | 'GBP' | 'CHF';
  timezone?: string;
  sourceKind: 'json' | 'csv' | 'woocommerce';
  sourceConfig: Record<string, unknown>;
  policy: TenantConfig['policy'];
  closes: TenantConfig['closes'];
  persona: TenantConfig['persona'];
  allowedOrigins: string[];
}

export interface ProvisionResult {
  ok: boolean;
  tenantId?: string;
  slug?: string;
  embedSnippet?: string;
  itemCount?: number;
  sample?: CatalogItem[];
  error?: string;
  issues?: unknown[];
}

export class OnboardingService {
  private jsonSource = new JsonCatalogSource();
  private csvSource = new CsvCatalogSource();
  private wooSource = new WooCommerceCatalogSource();

  constructor(
    private tenantRepo: TenantRepository,
    private catalogRepo: CatalogRepository
  ) {}

  async verifySource(
    sourceKind: 'json' | 'csv' | 'woocommerce',
    sourceConfig: unknown
  ): Promise<VerifyResult> {
    switch (sourceKind) {
      case 'json':
        return await this.jsonSource.verify(sourceConfig);
      case 'csv':
        return await this.csvSource.verify(sourceConfig);
      case 'woocommerce':
        return await this.wooSource.verify(sourceConfig);
      default:
        return {
          ok: false,
          itemCount: 0,
          sample: [],
          warnings: [`Unknown catalog source kind: ${sourceKind}`]
        };
    }
  }

  async provisionTenant(draft: OnboardingDraft): Promise<ProvisionResult> {
    const tenantId = crypto.randomUUID();

    // 1. Construct and validate full TenantConfig
    const candidateConfig: TenantConfig = {
      version: 1,
      tenantId,
      displayName: draft.displayName,
      tier: draft.tier || 'standard',
      locales: draft.locales || ['pt-PT', 'en'],
      currency: draft.currency || 'EUR',
      timezone: draft.timezone || 'Europe/Lisbon',
      persona: draft.persona,
      catalog: {
        source: draft.sourceKind,
        config: draft.sourceConfig,
        refresh: {
          mode: draft.sourceKind === 'woocommerce' ? 'webhook' : 'poll',
          ttlMinutes: 60
        },
        staleness: {
          maxAgeMinutes: 240,
          onStale: 'hedge_price'
        }
      },
      policy: draft.policy,
      closes: draft.closes,
      channels: [
        {
          kind: 'web',
          allowedOrigins: draft.allowedOrigins
        }
      ],
      limits: {
        conversationsPerMonth: 500,
        tokenBudgetPerSession: 40000,
        monthlySpendCapEur: 25
      },
      compliance: {
        aiDisclosure: true,
        retentionDays: 30
      }
    };

    const validation = TenantConfigSchema.safeParse(candidateConfig);
    if (!validation.success) {
      return {
        ok: false,
        error: 'Invalid TenantConfig schema in onboarding draft.',
        issues: validation.error.issues
      };
    }

    const validatedConfig = validation.data;

    // 2. Fetch and persist initial catalog snapshot
    let catalog;
    try {
      const sourceConfigWithTenant = {
        ...draft.sourceConfig,
        tenantId
      };

      if (draft.sourceKind === 'json') {
        catalog = await this.jsonSource.fetch(sourceConfigWithTenant);
      } else if (draft.sourceKind === 'csv') {
        catalog = await this.csvSource.fetch(sourceConfigWithTenant);
      } else {
        catalog = await this.wooSource.fetch(sourceConfigWithTenant);
      }
    } catch (err: unknown) {
      return {
        ok: false,
        error: `Failed to fetch catalog from ${draft.sourceKind}: ${(err as Error).message}`
      };
    }

    // 3. Upsert tenant in database
    await this.tenantRepo.upsert({
      id: tenantId,
      slug: draft.slug,
      displayName: draft.displayName,
      config: validatedConfig
    });

    // 4. Save initial catalog snapshot
    await this.catalogRepo.saveSnapshot(tenantId, catalog);

    // 5. Generate embed script snippet
    const embedSnippet = `<script src="https://agent.rewilt.com/widget.js" data-tenant-id="${tenantId}" defer></script>`;

    return {
      ok: true,
      tenantId,
      slug: draft.slug,
      embedSnippet,
      itemCount: catalog.items.length,
      sample: catalog.items.slice(0, 5)
    };
  }
}
