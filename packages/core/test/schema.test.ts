import { describe, it, expect } from 'vitest';
import {
  tenants,
  catalogSnapshots,
  catalogItems,
  sessions,
  messages,
  toolCalls,
  leads,
  subscriptions,
  evalRuns
} from '../src/db/schema.js';
import {
  REWILT_TENANT_ID,
  REWILT_TENANT_CONFIG,
  REWILT_CATALOG
} from '../src/db/seed.js';
import { TenantConfigSchema, CatalogSchema } from '@salesops/types';
import { getTableColumns } from 'drizzle-orm';

describe('Database Schema & Seed Validation', () => {
  it('ensures all 9 tables are defined with required tenantId / primary keys', () => {
    const allTables = [
      { name: 'tenants', table: tenants, requiresTenantId: false },
      { name: 'catalog_snapshots', table: catalogSnapshots, requiresTenantId: true },
      { name: 'catalog_items', table: catalogItems, requiresTenantId: true },
      { name: 'sessions', table: sessions, requiresTenantId: true },
      { name: 'messages', table: messages, requiresTenantId: true },
      { name: 'tool_calls', table: toolCalls, requiresTenantId: true },
      { name: 'leads', table: leads, requiresTenantId: true },
      { name: 'subscriptions', table: subscriptions, requiresTenantId: true },
      { name: 'eval_runs', table: evalRuns, requiresTenantId: true }
    ];

    expect(allTables.length).toBe(9);

    for (const { name, table, requiresTenantId } of allTables) {
      const cols = getTableColumns(table) as Record<string, unknown>;
      expect(cols.id, `Table ${name} must have an 'id' primary key column`).toBeDefined();

      if (requiresTenantId) {
        expect(
          cols.tenantId,
          `Table ${name} must have a 'tenantId' column for strict tenant isolation.`
        ).toBeDefined();
      }
    }
  });

  it('validates rewilt tenant seed configuration against TenantConfigSchema', () => {
    expect(REWILT_TENANT_ID).toBe('00000000-0000-4000-8000-000000000001');

    const result = TenantConfigSchema.safeParse(REWILT_TENANT_CONFIG);
    expect(result.success).toBe(true);

    if (result.success) {
      expect(result.data.compliance.aiDisclosure).toBe(true);
      expect(result.data.tier).toBe('standard');
      expect(result.data.closes.length).toBeGreaterThanOrEqual(1);
    }
  });

  it('validates rewilt seed catalog against CatalogSchema', () => {
    const result = CatalogSchema.safeParse(REWILT_CATALOG);
    expect(result.success).toBe(true);

    if (result.success) {
      expect(result.data.items.length).toBe(5);
      expect(result.data.items.map((i) => i.sku)).toEqual([
        'salesops_lite',
        'salesops_standard',
        'salesops_europe',
        'salesops_premium',
        'salesops_preview'
      ]);
    }
  });
});
