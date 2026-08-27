import type { Catalog, CatalogSource } from '@salesops/types';
import type { CatalogRepository, EvalRunRepository } from '../db/repositories.js';

export interface SmokeEvaluator {
  runSmokeEvals(catalog: Catalog): Promise<{
    ok: boolean;
    total: number;
    passed: number;
    failed: number;
    suiteResult: Record<string, unknown>;
  }>;
}

export interface CatalogSyncOptions {
  tenantId: string;
  source: CatalogSource;
  sourceConfig: unknown;
  smokeEvaluator?: SmokeEvaluator;
}

export interface CatalogSyncResult {
  success: boolean;
  snapshotId?: string;
  itemCount: number;
  smokePassed?: boolean;
  error?: string;
  smokeResult?: Record<string, unknown>;
}

export class CatalogSyncService {
  constructor(
    private catalogRepo: CatalogRepository,
    private evalRunRepo?: EvalRunRepository
  ) {}

  async syncAndActivate(options: CatalogSyncOptions): Promise<CatalogSyncResult> {
    try {
      // 1. Fetch raw catalog from source adapter
      const catalog = await options.source.fetch(options.sourceConfig);

      // 2. Run automated smoke evaluation gate (if evaluator provided)
      let smokePassed = true;
      let smokeResultDetail: Record<string, unknown> | undefined;

      if (options.smokeEvaluator) {
        const smokeResult = await options.smokeEvaluator.runSmokeEvals(catalog);
        smokePassed = smokeResult.ok;
        smokeResultDetail = smokeResult.suiteResult;

        // Log smoke eval run to database
        if (this.evalRunRepo) {
          await this.evalRunRepo.recordRun({
            tenantId: options.tenantId,
            suite: 'catalog_smoke',
            passed: smokeResult.passed,
            failed: smokeResult.failed,
            detail: smokeResult.suiteResult
          });
        }

        // Gate: Block snapshot activation if smoke test failed
        if (!smokePassed) {
          return {
            success: false,
            itemCount: catalog.items.length,
            smokePassed: false,
            error: `Catalog snapshot activation blocked: Smoke eval suite failed (${smokeResult.failed}/${smokeResult.total} failed).`,
            smokeResult: smokeResultDetail
          };
        }
      }

      // 3. Persist new active snapshot & supersede prior snapshot
      const snapshot = await this.catalogRepo.saveSnapshot(options.tenantId, catalog);

      return {
        success: true,
        snapshotId: snapshot.id,
        itemCount: catalog.items.length,
        smokePassed
      };
    } catch (err: unknown) {
      return {
        success: false,
        itemCount: 0,
        error: (err as Error).message
      };
    }
  }
}
