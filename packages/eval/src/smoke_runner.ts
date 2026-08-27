import type { Catalog } from '@salesops/types';
import type { AgentTurnExecutor } from '@salesops/core';
import { EvalRunner } from './runner.js';
import { generateCatalogSmokeSuite } from './suites/smoke_generator.js';
import type { EvalSuiteResult } from './types.js';

export interface SmokeRunnerOptions {
  executor: AgentTurnExecutor;
  tenantId: string;
}

export interface SmokeRunnerResult {
  ok: boolean;
  total: number;
  passed: number;
  failed: number;
  suiteResult: EvalSuiteResult;
}

export class CatalogSmokeRunner {
  private runner: EvalRunner;
  private tenantId: string;

  constructor(options: SmokeRunnerOptions) {
    this.runner = new EvalRunner({
      executor: options.executor,
      tenantId: options.tenantId
    });
    this.tenantId = options.tenantId;
  }

  async runSmokeEvals(catalog: Catalog): Promise<SmokeRunnerResult> {
    const cases = generateCatalogSmokeSuite(catalog);
    const suiteResult = await this.runner.runSuite('catalog_smoke', cases);

    const ok = suiteResult.failed === 0 && suiteResult.passed > 0;

    return {
      ok,
      total: suiteResult.total,
      passed: suiteResult.passed,
      failed: suiteResult.failed,
      suiteResult
    };
  }
}
