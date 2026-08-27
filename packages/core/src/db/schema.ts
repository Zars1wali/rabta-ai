import {
  pgTable,
  uuid,
  text,
  jsonb,
  timestamp,
  integer,
  bigint,
  boolean,
  index
} from 'drizzle-orm/pg-core';
import type { TenantConfig, CatalogItem } from '@salesops/types';

export const tenants = pgTable('tenants', {
  id: uuid('id').primaryKey().defaultRandom(),
  slug: text('slug').notNull().unique(),
  displayName: text('display_name').notNull(),
  config: jsonb('config').$type<TenantConfig>().notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
});

export const catalogSnapshots = pgTable(
  'catalog_snapshots',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    sourceKind: text('source_kind').notNull(),
    fetchedAt: timestamp('fetched_at', { withTimezone: true }).notNull(),
    itemCount: integer('item_count').notNull(),
    status: text('status').notNull().default('active'), // 'active' | 'superseded' | 'failed'
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('catalog_snapshots_tenant_status_idx').on(table.tenantId, table.status, table.fetchedAt)
  ]
);

export const catalogItems = pgTable(
  'catalog_items',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    snapshotId: uuid('snapshot_id')
      .notNull()
      .references(() => catalogSnapshots.id, { onDelete: 'cascade' }),
    sku: text('sku').notNull(),
    name: text('name').notNull(),
    category: text('category'),
    description: text('description'),
    priceMinor: bigint('price_minor', { mode: 'number' }).notNull(),
    currency: text('currency').notNull(),
    billing: text('billing').notNull().default('month'),
    attributes: jsonb('attributes').$type<CatalogItem['attributes']>().notNull().default({}),
    available: boolean('available').notNull().default(true),
    url: text('url')
  },
  (table) => [
    index('catalog_items_tenant_snapshot_idx').on(table.tenantId, table.snapshotId),
    index('catalog_items_sku_idx').on(table.tenantId, table.sku)
  ]
);

export const sessions = pgTable(
  'sessions',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    channel: text('channel').notNull(),
    externalRef: text('external_ref'),
    stage: text('stage').notNull().default('greet'),
    locale: text('locale').notNull().default('en'),
    consentAt: timestamp('consent_at', { withTimezone: true }),
    tokensUsed: integer('tokens_used').notNull().default(0),
    costMinor: integer('cost_minor').notNull().default(0),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    lastMessageAt: timestamp('last_message_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [index('sessions_tenant_last_msg_idx').on(table.tenantId, table.lastMessageAt)]
);

export const messages = pgTable(
  'messages',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    sessionId: uuid('session_id')
      .notNull()
      .references(() => sessions.id, { onDelete: 'cascade' }),
    role: text('role').notNull(), // 'visitor' | 'agent' | 'human' | 'system' | 'tool'
    content: text('content'),
    mediaUrl: text('media_url'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [index('messages_session_created_idx').on(table.sessionId, table.createdAt)]
);

export const toolCalls = pgTable(
  'tool_calls',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    sessionId: uuid('session_id')
      .notNull()
      .references(() => sessions.id, { onDelete: 'cascade' }),
    name: text('name').notNull(),
    input: jsonb('input').$type<Record<string, unknown>>().notNull(),
    output: jsonb('output').$type<Record<string, unknown>>().notNull(),
    ok: boolean('ok').notNull(),
    latencyMs: integer('latency_ms').notNull(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [index('tool_calls_session_created_idx').on(table.sessionId, table.createdAt)]
);

export const leads = pgTable(
  'leads',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    sessionId: uuid('session_id')
      .notNull()
      .references(() => sessions.id, { onDelete: 'cascade' }),
    name: text('name'),
    email: text('email'),
    phone: text('phone'),
    companyUrl: text('company_url'),
    notes: text('notes'),
    consentAt: timestamp('consent_at', { withTimezone: true }).notNull(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [index('leads_tenant_created_idx').on(table.tenantId, table.createdAt)]
);

export const subscriptions = pgTable(
  'subscriptions',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    sessionId: uuid('session_id').references(() => sessions.id),
    stripeCustomerId: text('stripe_customer_id').notNull(),
    stripeSubscriptionId: text('stripe_subscription_id').unique(),
    stripeCheckoutId: text('stripe_checkout_id').unique(),
    kind: text('kind').notNull(), // 'subscription' | 'preview'
    status: text('status').notNull(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [index('subscriptions_tenant_created_idx').on(table.tenantId, table.createdAt)]
);

export const evalRuns = pgTable(
  'eval_runs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    suite: text('suite').notNull(),
    passed: integer('passed').notNull(),
    failed: integer('failed').notNull(),
    detail: jsonb('detail').$type<Record<string, unknown>>().notNull(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [index('eval_runs_tenant_created_idx').on(table.tenantId, table.createdAt)]
);

export const entitlements = pgTable(
  'entitlements',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    periodStart: timestamp('period_start', { withTimezone: true }).notNull(),
    periodEnd: timestamp('period_end', { withTimezone: true }).notNull(),
    includedConversations: integer('included_conversations').notNull().default(500),
    overageRateMinor: integer('overage_rate_minor').notNull().default(10), // e.g. 10 cents per additional conversation
    overageCapMinor: integer('overage_cap_minor').notNull().default(5000), // €50 max overage
    status: text('status').notNull().default('active'), // 'active' | 'expired'
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [index('entitlements_tenant_period_idx').on(table.tenantId, table.periodStart, table.status)]
);

export const usageEvents = pgTable(
  'usage_events',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    windowId: text('window_id').notNull().unique(), // e.g. "web:<hash>:2026-08-27T14"
    identityHash: text('identity_hash').notNull(),
    channel: text('channel').notNull(),
    windowStart: timestamp('window_start', { withTimezone: true }).notNull(),
    windowEnd: timestamp('window_end', { withTimezone: true }).notNull(),
    firstSeenAt: timestamp('first_seen_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('usage_events_tenant_window_idx').on(table.tenantId, table.windowStart, table.windowEnd),
    index('usage_events_identity_idx').on(table.tenantId, table.identityHash, table.windowEnd)
  ]
);

export const usageCounters = pgTable(
  'usage_counters',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    periodStart: timestamp('period_start', { withTimezone: true }).notNull(),
    conversationsUsed: integer('conversations_used').notNull().default(0),
    tokensUsed: integer('tokens_used').notNull().default(0),
    lastEventAt: timestamp('last_event_at', { withTimezone: true }),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('usage_counters_tenant_period_idx').on(table.tenantId, table.periodStart)
  ]
);

export const depletionAlerts = pgTable(
  'depletion_alerts',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    periodStart: timestamp('period_start', { withTimezone: true }).notNull(),
    threshold: integer('threshold').notNull(), // 80, 100, 120 (%)
    triggeredAt: timestamp('triggered_at', { withTimezone: true }).notNull().defaultNow(),
    channel: text('channel').notNull().default('email')
  },
  (table) => [
    index('depletion_alerts_tenant_threshold_idx').on(table.tenantId, table.periodStart, table.threshold)
  ]
);

