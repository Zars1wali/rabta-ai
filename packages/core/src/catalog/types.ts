import type { CatalogItem } from '@salesops/types';

export type CatalogStalenessState = 'fresh' | 'stale';

export interface StalenessEvaluation {
  state: CatalogStalenessState;
  ageMinutes: number;
  maxAgeMinutes: number;
  action: 'none' | 'hedge_price' | 'refuse';
  disclaimer: string | null;
}

export interface CatalogItemWithStaleness extends CatalogItem {
  isStale: boolean;
  stalenessDisclaimer: string | null;
}
