/**
 * PostgreSQL Row-Level Security (RLS) Engine for Nuncio / ZeroPointIntel.
 *
 * Enforces strict multi-tenant isolation at the database engine level.
 * Even if an application query omits `WHERE tenant_id = ...`, PostgreSQL will
 * refuse to return or modify any rows belonging to other tenants.
 */

export const TENANT_SCOPED_TABLES = [
  'channels',
  'contacts',
  'conversations',
  'messages',
  'offerings',
  'leads',
  'quote_requests',
  'orders',
  'payments',
  'timeline_events',
  'ai_runs',
  'memberships',
  'catalog_snapshots',
  'catalog_items',
  'sessions',
  'tool_calls',
  'subscriptions',
  'entitlements',
  'usage_events',
  'usage_counters',
  'depletion_alerts',
  'spend_ledger'
] as const;

export type TenantScopedTable = (typeof TENANT_SCOPED_TABLES)[number];

export interface RlsConfig {
  sessionVariable?: string; // default: 'app.current_tenant_id'
  policyName?: string; // default: 'tenant_isolation_policy'
}

/**
 * Generates the authoritative PostgreSQL DDL statements to enable RLS
 * and apply strict tenant isolation policies across all tenant-scoped tables.
 */
export function generateRlsSql(config?: RlsConfig): string[] {
  const sessionVar = config?.sessionVariable || 'app.current_tenant_id';
  const policyName = config?.policyName || 'tenant_isolation_policy';

  const statements: string[] = [];

  for (const table of TENANT_SCOPED_TABLES) {
    // 1. Enable RLS on table
    statements.push(`ALTER TABLE "${table}" ENABLE ROW LEVEL SECURITY;`);

    // 2. Force RLS for table owners / superusers within application connections
    statements.push(`ALTER TABLE "${table}" FORCE ROW LEVEL SECURITY;`);

    // 3. Drop existing policy if present
    statements.push(`DROP POLICY IF EXISTS "${policyName}" ON "${table}";`);

    // 4. Create comprehensive isolation policy for SELECT, INSERT, UPDATE, DELETE
    statements.push(
      `CREATE POLICY "${policyName}" ON "${table}" ` +
        `FOR ALL ` +
        `USING (tenant_id = NULLIF(current_setting('${sessionVar}', true), '')::uuid) ` +
        `WITH CHECK (tenant_id = NULLIF(current_setting('${sessionVar}', true), '')::uuid);`
    );
  }

  return statements;
}

/**
 * Returns SQL to set the tenant context for the current database transaction.
 */
export function getTenantContextSql(tenantId: string, sessionVariable = 'app.current_tenant_id'): string {
  // Validate UUID format to prevent SQL injection in raw SET statements
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  if (!uuidRegex.test(tenantId)) {
    throw new Error(`Invalid tenant ID format for RLS context: "${tenantId}"`);
  }
  return `SET LOCAL ${sessionVariable} = '${tenantId}';`;
}

/**
 * Interface for database executors supporting raw SQL queries or transactions.
 */
export interface SqlExecutor {
  execute(query: string | { text: string; values?: unknown[] }): Promise<unknown>;
}

/**
 * Executes a function within a strict PostgreSQL tenant context transaction.
 */
export async function withTenantContext<T, D extends SqlExecutor>(
  db: D,
  tenantId: string,
  fn: (db: D) => Promise<T>,
  sessionVariable = 'app.current_tenant_id'
): Promise<T> {
  const setSql = getTenantContextSql(tenantId, sessionVariable);
  await db.execute(setSql);
  return await fn(db);
}
