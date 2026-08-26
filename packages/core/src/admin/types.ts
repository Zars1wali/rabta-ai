import type { TenantConfig } from '@salesops/types';

export interface TenantSummary {
  id: string;
  slug: string;
  displayName: string;
  config: TenantConfig;
  createdAt: string;
  updatedAt: string;
}

export interface UpdateTenantConfigOptions {
  tenantId: string;
  config: TenantConfig;
  displayName?: string;
  expectedVersion?: number;
  updatedBy?: string;
  changeSummary?: string;
}

export interface CreateTenantOptions {
  id?: string;
  slug: string;
  displayName: string;
  config: TenantConfig;
}

export interface TenantAdminResult {
  ok: boolean;
  tenant?: TenantSummary;
  error?: string;
  issues?: unknown[];
}
