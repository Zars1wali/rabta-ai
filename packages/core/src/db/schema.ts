import {
  pgTable,
  uuid,
  text,
  jsonb,
  timestamp,
  integer,
  bigint,
  boolean,
  doublePrecision,
  index,
  uniqueIndex
} from 'drizzle-orm/pg-core';
import type {
  TenantConfig,
  CatalogItem,
  UserRole,
  LeadState,
  LeadType,
  ChannelType,
  ConversationStatus,
  AiMode,
  MessageDirection,
  MessageType,
  MessageBillingCategory,
  PriceType,
  OrderStatus,
  OrderLineItem,
  QuoteRequestFields,
  AiRunOutcome
} from '@salesops/types';

// ==========================================
// 1. TENANCY & USERS
// ==========================================

export const tenants = pgTable('tenants', {
  id: uuid('id').primaryKey().defaultRandom(),
  slug: text('slug').notNull().unique(),
  displayName: text('display_name').notNull(),
  legalName: text('legal_name'),
  country: text('country').default('CH'),
  verticalPackId: text('vertical_pack_id').default('swiss_cleaning'),
  timezone: text('timezone').default('Europe/Zurich'),
  defaultLanguage: text('default_language').default('de'),
  status: text('status').notNull().default('active'),
  plan: text('plan').notNull().default('starter'),
  config: jsonb('config').$type<TenantConfig>().notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
});

export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  email: text('email').notNull().unique(),
  name: text('name'),
  passwordHash: text('password_hash'),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
});

export const memberships = pgTable(
  'memberships',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    userId: uuid('user_id')
      .notNull()
      .references(() => users.id, { onDelete: 'cascade' }),
    role: text('role').$type<UserRole>().notNull().default('agent'), // 'owner' | 'agent' | 'viewer'
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('memberships_tenant_user_idx').on(table.tenantId, table.userId),
    index('memberships_user_role_idx').on(table.userId, table.role)
  ]
);

// ==========================================
// 2. CHANNELS, CONTACTS & CONVERSATIONS
// ==========================================

export const channels = pgTable(
  'channels',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    type: text('type').$type<ChannelType>().notNull().default('whatsapp'),
    wabaId: text('waba_id'),
    phoneNumberId: text('phone_number_id'),
    displayNumber: text('display_number'),
    status: text('status').notNull().default('active'), // 'active' | 'disconnected' | 'pending'
    tokenRef: text('token_ref'),
    config: jsonb('config').$type<Record<string, unknown>>().default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('channels_tenant_type_idx').on(table.tenantId, table.type),
    index('channels_phone_number_idx').on(table.phoneNumberId)
  ]
);

export const contacts = pgTable(
  'contacts',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    waId: text('wa_id'), // WhatsApp user ID / phone number
    displayName: text('display_name'),
    phoneE164: text('phone_e164'),
    language: text('language').notNull().default('de'), // DE, FR, IT, EN
    tags: jsonb('tags').$type<string[]>().notNull().default([]),
    consentSource: text('consent_source'),
    consentAt: timestamp('consent_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('contacts_tenant_wa_id_idx').on(table.tenantId, table.waId),
    index('contacts_tenant_phone_idx').on(table.tenantId, table.phoneE164)
  ]
);

export const conversations = pgTable(
  'conversations',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    channelId: uuid('channel_id')
      .notNull()
      .references(() => channels.id, { onDelete: 'cascade' }),
    contactId: uuid('contact_id')
      .notNull()
      .references(() => contacts.id, { onDelete: 'cascade' }),
    status: text('status').$type<ConversationStatus>().notNull().default('open'), // 'open' | 'snoozed' | 'closed'
    serviceWindowExpiresAt: timestamp('service_window_expires_at', { withTimezone: true }),
    aiMode: text('ai_mode').$type<AiMode>().notNull().default('suggest'), // 'off' | 'suggest' | 'auto'
    lastMessageAt: timestamp('last_message_at', { withTimezone: true }).notNull().defaultNow(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('conversations_tenant_contact_idx').on(table.tenantId, table.contactId),
    index('conversations_tenant_last_msg_idx').on(table.tenantId, table.lastMessageAt)
  ]
);

export const messages = pgTable(
  'messages',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    conversationId: uuid('conversation_id')
      .references(() => conversations.id, { onDelete: 'cascade' }),
    sessionId: uuid('session_id')
      .references(() => sessions.id, { onDelete: 'cascade' }),
    role: text('role'), // 'visitor' | 'agent' | 'human' | 'system' | 'tool'
    content: text('content'),
    direction: text('direction').$type<MessageDirection>(), // 'inbound' | 'outbound'
    wamid: text('wamid'), // WhatsApp message ID for strict idempotency
    type: text('type').$type<MessageType>().notNull().default('text'), // 'text' | 'audio' | 'image' | 'document' | 'interactive'
    body: text('body'),
    mediaUrl: text('media_url'),
    billingCategory: text('billing_category').$type<MessageBillingCategory>().notNull().default('service'),
    costEstimateMinor: integer('cost_estimate_minor').notNull().default(0),
    author: text('author').notNull().default('agent'), // 'customer' | 'agent' | 'human_agent' | 'system'
    rawPayload: jsonb('raw_payload').$type<Record<string, unknown>>(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    uniqueIndex('messages_wamid_unique_idx').on(table.wamid),
    index('messages_conversation_created_idx').on(table.conversationId, table.createdAt),
    index('messages_session_created_idx').on(table.sessionId, table.createdAt),
    index('messages_tenant_created_idx').on(table.tenantId, table.createdAt)
  ]
);

// ==========================================
// 3. COMMERCIAL ENGINE: LEADS, CATALOG & ORDERS
// ==========================================

export const offerings = pgTable(
  'offerings',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    sku: text('sku').notNull(),
    name: text('name').notNull(),
    description: text('description'),
    priceType: text('price_type').$type<PriceType>().notNull().default('fixed'),
    priceMinor: bigint('price_minor', { mode: 'number' }).notNull(),
    currency: text('currency').notNull().default('CHF'),
    serviceArea: text('service_area'),
    durationMinutes: integer('duration_minutes'),
    active: boolean('active').notNull().default(true),
    attributes: jsonb('attributes').$type<Record<string, unknown>>().notNull().default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('offerings_tenant_sku_idx').on(table.tenantId, table.sku),
    index('offerings_tenant_active_idx').on(table.tenantId, table.active)
  ]
);

export const leads = pgTable(
  'leads',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    contactId: uuid('contact_id')
      .references(() => contacts.id, { onDelete: 'cascade' }),
    sessionId: uuid('session_id')
      .references(() => sessions.id, { onDelete: 'cascade' }),
    name: text('name'),
    email: text('email'),
    phone: text('phone'),
    companyUrl: text('company_url'),
    notes: text('notes'),
    consentAt: timestamp('consent_at', { withTimezone: true }),
    conversationId: uuid('conversation_id').references(() => conversations.id, { onDelete: 'set null' }),
    leadType: text('lead_type').$type<LeadType>().notNull().default('quote_request'),
    state: text('state').$type<LeadState>().notNull().default('new'), // 'new' -> 'qualifying' -> 'interested' -> 'quoted' -> 'order_pending' -> 'won' | 'lost' | 'dormant'
    score: integer('score').notNull().default(50),
    valueEstimateMinor: integer('value_estimate_minor').notNull().default(0),
    currency: text('currency').notNull().default('CHF'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('leads_tenant_state_idx').on(table.tenantId, table.state),
    index('leads_tenant_contact_idx').on(table.tenantId, table.contactId),
    index('leads_tenant_created_idx').on(table.tenantId, table.createdAt)
  ]
);

export const quoteRequests = pgTable(
  'quote_requests',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    leadId: uuid('lead_id')
      .notNull()
      .references(() => leads.id, { onDelete: 'cascade' }),
    fields: jsonb('fields').$type<QuoteRequestFields>().notNull().default({}),
    completeness: doublePrecision('completeness').notNull().default(0.0), // 0.0 to 1.0
    missingFields: jsonb('missing_fields').$type<string[]>().notNull().default([]),
    suggestedPackage: text('suggested_package'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('quote_requests_tenant_lead_idx').on(table.tenantId, table.leadId)
  ]
);

export const orders = pgTable(
  'orders',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    leadId: uuid('lead_id')
      .notNull()
      .references(() => leads.id, { onDelete: 'cascade' }),
    contactId: uuid('contact_id')
      .notNull()
      .references(() => contacts.id, { onDelete: 'cascade' }),
    lineItems: jsonb('line_items').$type<OrderLineItem[]>().notNull().default([]),
    status: text('status').$type<OrderStatus>().notNull().default('draft'), // 'draft' | 'pending' | 'paid' | 'cancelled'
    amountMinor: integer('amount_minor').notNull().default(0),
    currency: text('currency').notNull().default('CHF'),
    stripePaymentIntentId: text('stripe_payment_intent_id'),
    stripeCheckoutId: text('stripe_checkout_id'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('orders_tenant_lead_idx').on(table.tenantId, table.leadId),
    index('orders_tenant_status_idx').on(table.tenantId, table.status)
  ]
);

export const payments = pgTable(
  'payments',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    orderId: uuid('order_id')
      .notNull()
      .references(() => orders.id, { onDelete: 'cascade' }),
    stripePaymentIntentId: text('stripe_payment_intent_id').notNull(),
    amountMinor: integer('amount_minor').notNull(),
    currency: text('currency').notNull().default('CHF'),
    status: text('status').notNull().default('succeeded'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('payments_tenant_order_idx').on(table.tenantId, table.orderId)
  ]
);

export const timelineEvents = pgTable(
  'timeline_events',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    aggregateType: text('aggregate_type').notNull(), // 'lead' | 'conversation' | 'order' | 'contact'
    aggregateId: uuid('aggregate_id').notNull(),
    eventType: text('event_type').notNull(),
    payload: jsonb('payload').$type<Record<string, unknown>>().notNull().default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('timeline_events_aggregate_idx').on(table.tenantId, table.aggregateType, table.aggregateId, table.createdAt)
  ]
);

export const aiRuns = pgTable(
  'ai_runs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    conversationId: uuid('conversation_id').notNull(),
    messageId: uuid('message_id'),
    model: text('model').notNull(),
    inputTokens: integer('input_tokens').notNull().default(0),
    outputTokens: integer('output_tokens').notNull().default(0),
    latencyMs: integer('latency_ms').notNull().default(0),
    promptRef: text('prompt_ref'),
    outcome: text('outcome').$type<AiRunOutcome>().notNull().default('drafted'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('ai_runs_tenant_created_idx').on(table.tenantId, table.createdAt)
  ]
);

// ==========================================
// 4. LEGACY / METERING & BILLING TABLES
// ==========================================

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
    status: text('status').notNull().default('active'),
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
    kind: text('kind').notNull(),
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
    overageRateMinor: integer('overage_rate_minor').notNull().default(10),
    overageCapMinor: integer('overage_cap_minor').notNull().default(5000),
    status: text('status').notNull().default('active'),
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
    windowId: text('window_id').notNull().unique(),
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
    threshold: integer('threshold').notNull(),
    triggeredAt: timestamp('triggered_at', { withTimezone: true }).notNull().defaultNow(),
    channel: text('channel').notNull().default('email')
  },
  (table) => [
    index('depletion_alerts_tenant_threshold_idx').on(table.tenantId, table.periodStart, table.threshold)
  ]
);

export const spendLedger = pgTable(
  'spend_ledger',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    tenantId: uuid('tenant_id')
      .notNull()
      .references(() => tenants.id, { onDelete: 'cascade' }),
    entryType: text('entry_type').notNull(),
    amountMinor: integer('amount_minor').notNull(),
    balanceAfterMinor: integer('balance_after_minor').notNull(),
    model: text('model'),
    inputTokens: integer('input_tokens').default(0),
    outputTokens: integer('output_tokens').default(0),
    sessionId: text('session_id'),
    reference: text('reference'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow()
  },
  (table) => [
    index('spend_ledger_tenant_idx').on(table.tenantId, table.createdAt)
  ]
);
