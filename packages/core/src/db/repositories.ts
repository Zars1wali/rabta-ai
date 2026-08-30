import { eq, and, desc, sql, ilike } from 'drizzle-orm';
import type { Database } from './client.js';
import {
  tenants,
  catalogSnapshots,
  catalogItems,
  sessions,
  messages,
  toolCalls,
  leads,
  subscriptions,
  evalRuns,
  users,
  memberships,
  channels,
  contacts,
  conversations,
  offerings,
  quoteRequests,
  orders,
  payments,
  timelineEvents,
  aiRuns
} from './schema.js';
import type {
  TenantConfig,
  Catalog,
  CatalogItem,
  AgentMessage,
  Lead as LegacyLead,
  FunnelStage,
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

export class TenantRepository {
  constructor(private db: Database) {}

  async getById(tenantId: string) {
    const result = await this.db
      .select()
      .from(tenants)
      .where(eq(tenants.id, tenantId))
      .limit(1);
    return result[0] ?? null;
  }

  async getBySlug(slug: string) {
    const result = await this.db
      .select()
      .from(tenants)
      .where(eq(tenants.slug, slug))
      .limit(1);
    return result[0] ?? null;
  }

  async upsert(tenant: { id?: string; slug: string; displayName: string; config: TenantConfig }) {
    const result = await this.db
      .insert(tenants)
      .values({
        id: tenant.id,
        slug: tenant.slug,
        displayName: tenant.displayName,
        config: tenant.config
      })
      .onConflictDoUpdate({
        target: tenants.slug,
        set: {
          displayName: tenant.displayName,
          config: tenant.config,
          updatedAt: new Date()
        }
      })
      .returning();
    return result[0]!;
  }
}

export class CatalogRepository {
  constructor(private db: Database) {}

  async saveSnapshot(tenantId: string, catalog: Catalog) {
    return await this.db.transaction(async (tx) => {
      // 1. Mark existing active snapshots as superseded
      await tx
        .update(catalogSnapshots)
        .set({ status: 'superseded' })
        .where(
          and(
            eq(catalogSnapshots.tenantId, tenantId),
            eq(catalogSnapshots.status, 'active')
          )
        );

      // 2. Insert new snapshot
      const [snapshot] = await tx
        .insert(catalogSnapshots)
        .values({
          tenantId,
          sourceKind: catalog.sourceKind,
          fetchedAt: new Date(catalog.fetchedAt),
          itemCount: catalog.items.length,
          status: 'active'
        })
        .returning();

      if (!snapshot) {
        throw new Error('Failed to create catalog snapshot');
      }

      // 3. Insert items if any
      if (catalog.items.length > 0) {
        const itemRows = catalog.items.map((item) => ({
          tenantId,
          snapshotId: snapshot.id,
          sku: item.sku,
          name: item.name,
          category: item.category,
          description: item.description,
          priceMinor: item.priceMinor,
          currency: item.currency,
          billing: item.billing,
          attributes: item.attributes,
          available: item.available,
          url: item.url
        }));

        // Batch insert in chunks of 500
        const chunkSize = 500;
        for (let i = 0; i < itemRows.length; i += chunkSize) {
          const chunk = itemRows.slice(i, i + chunkSize);
          await tx.insert(catalogItems).values(chunk);
        }
      }

      return snapshot;
    });
  }

  async getActiveSnapshot(tenantId: string) {
    const [snapshot] = await this.db
      .select()
      .from(catalogSnapshots)
      .where(
        and(
          eq(catalogSnapshots.tenantId, tenantId),
          eq(catalogSnapshots.status, 'active')
        )
      )
      .orderBy(desc(catalogSnapshots.fetchedAt))
      .limit(1);

    if (!snapshot) return null;

    const items = await this.db
      .select()
      .from(catalogItems)
      .where(
        and(
          eq(catalogItems.tenantId, tenantId),
          eq(catalogItems.snapshotId, snapshot.id)
        )
      );

    return {
      snapshot,
      items: items.map(this.mapItemRowToCatalogItem)
    };
  }

  async searchItems(
    tenantId: string,
    options: {
      query?: string;
      category?: string;
      maxPriceMinor?: number;
      limit?: number;
    } = {}
  ): Promise<CatalogItem[]> {
    const [activeSnapshot] = await this.db
      .select({ id: catalogSnapshots.id })
      .from(catalogSnapshots)
      .where(
        and(
          eq(catalogSnapshots.tenantId, tenantId),
          eq(catalogSnapshots.status, 'active')
        )
      )
      .orderBy(desc(catalogSnapshots.fetchedAt))
      .limit(1);

    if (!activeSnapshot) return [];

    const conditions = [
      eq(catalogItems.tenantId, tenantId),
      eq(catalogItems.snapshotId, activeSnapshot.id),
      eq(catalogItems.available, true)
    ];

    if (options.category) {
      conditions.push(eq(catalogItems.category, options.category));
    }

    if (options.maxPriceMinor !== undefined) {
      conditions.push(sql`${catalogItems.priceMinor} <= ${options.maxPriceMinor}`);
    }

    if (options.query) {
      const pattern = `%${options.query}%`;
      conditions.push(
        sql`(${ilike(catalogItems.name, pattern)} OR ${ilike(catalogItems.description, pattern)} OR ${ilike(catalogItems.sku, pattern)})`
      );
    }

    const rows = await this.db
      .select()
      .from(catalogItems)
      .where(and(...conditions))
      .limit(options.limit ?? 20);

    return rows.map(this.mapItemRowToCatalogItem);
  }

  async getItemBySku(tenantId: string, sku: string): Promise<CatalogItem | null> {
    const [activeSnapshot] = await this.db
      .select({ id: catalogSnapshots.id })
      .from(catalogSnapshots)
      .where(
        and(
          eq(catalogSnapshots.tenantId, tenantId),
          eq(catalogSnapshots.status, 'active')
        )
      )
      .orderBy(desc(catalogSnapshots.fetchedAt))
      .limit(1);

    if (!activeSnapshot) return null;

    const [row] = await this.db
      .select()
      .from(catalogItems)
      .where(
        and(
          eq(catalogItems.tenantId, tenantId),
          eq(catalogItems.snapshotId, activeSnapshot.id),
          eq(catalogItems.sku, sku)
        )
      )
      .limit(1);

    return row ? this.mapItemRowToCatalogItem(row) : null;
  }

  private mapItemRowToCatalogItem(row: typeof catalogItems.$inferSelect): CatalogItem {
    return {
      sku: row.sku,
      name: row.name,
      category: row.category,
      description: row.description,
      priceMinor: row.priceMinor,
      currency: row.currency as CatalogItem['currency'],
      billing: row.billing as CatalogItem['billing'],
      attributes: row.attributes ?? {},
      available: row.available,
      url: row.url
    };
  }
}

export class SessionRepository {
  constructor(private db: Database) {}

  async createSession(input: {
    id?: string;
    tenantId: string;
    channel: string;
    externalRef?: string | null;
    stage?: FunnelStage;
    locale?: string;
  }) {
    const [session] = await this.db
      .insert(sessions)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        channel: input.channel,
        externalRef: input.externalRef,
        stage: input.stage ?? 'greet',
        locale: input.locale ?? 'en'
      })
      .returning();
    return session!;
  }

  async getSession(tenantId: string, sessionId: string) {
    const [session] = await this.db
      .select()
      .from(sessions)
      .where(and(eq(sessions.tenantId, tenantId), eq(sessions.id, sessionId)))
      .limit(1);
    return session ?? null;
  }

  async updateTurn(
    tenantId: string,
    sessionId: string,
    data: {
      stage: FunnelStage;
      tokensUsed?: number;
      costMinor?: number;
    }
  ) {
    const tokens = data.tokensUsed ?? 0;
    const cost = data.costMinor ?? 0;
    const [updated] = await this.db
      .update(sessions)
      .set({
        stage: data.stage,
        tokensUsed: sql`${sessions.tokensUsed} + ${tokens}`,
        costMinor: sql`${sessions.costMinor} + ${cost}`,
        lastMessageAt: new Date()
      })
      .where(and(eq(sessions.tenantId, tenantId), eq(sessions.id, sessionId)))
      .returning();
    return updated ?? null;
  }
}

export class MessageRepository {
  constructor(private db: Database) {}

  async addMessage(input: {
    id?: string;
    tenantId: string;
    sessionId: string;
    role: 'visitor' | 'agent' | 'human' | 'system' | 'tool';
    content: string;
    mediaUrl?: string | null;
  }) {
    const [message] = await this.db
      .insert(messages)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        sessionId: input.sessionId,
        role: input.role,
        content: input.content,
        mediaUrl: input.mediaUrl
      })
      .returning();
    return message!;
  }

  async getRecentHistory(tenantId: string, sessionId: string, limit = 15): Promise<AgentMessage[]> {
    const rows = await this.db
      .select()
      .from(messages)
      .where(and(eq(messages.tenantId, tenantId), eq(messages.sessionId, sessionId)))
      .orderBy(desc(messages.createdAt))
      .limit(limit);

    // Return in chronological order
    return rows.reverse().map((r) => ({
      id: r.id,
      role: (r.role ?? 'visitor') as AgentMessage['role'],
      content: r.content ?? r.body ?? '',
      mediaUrl: r.mediaUrl,
      createdAt: r.createdAt.toISOString()
    }));
  }
}

export class ToolCallRepository {
  constructor(private db: Database) {}

  async recordToolCall(input: {
    tenantId: string;
    sessionId: string;
    name: string;
    input: Record<string, unknown>;
    output: Record<string, unknown>;
    ok: boolean;
    latencyMs: number;
  }) {
    const [record] = await this.db
      .insert(toolCalls)
      .values({
        tenantId: input.tenantId,
        sessionId: input.sessionId,
        name: input.name,
        input: input.input,
        output: input.output,
        ok: input.ok,
        latencyMs: input.latencyMs
      })
      .returning();
    return record!;
  }
}

export class LeadRepository {
  constructor(private db: Database) {}

  async createLead(input: {
    id?: string;
    tenantId: string;
    sessionId: string;
    name?: string | null;
    email?: string | null;
    phone?: string | null;
    companyUrl?: string | null;
    notes?: string | null;
    consentAt: Date;
  }): Promise<LegacyLead> {
    const [lead] = await this.db
      .insert(leads)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        sessionId: input.sessionId,
        name: input.name,
        email: input.email,
        phone: input.phone,
        companyUrl: input.companyUrl,
        notes: input.notes,
        consentAt: input.consentAt
      })
      .returning();

    return {
      id: lead!.id,
      tenantId: lead!.tenantId,
      sessionId: lead!.sessionId ?? '',
      name: lead!.name,
      email: lead!.email,
      phone: lead!.phone,
      companyUrl: lead!.companyUrl,
      notes: lead!.notes,
      consentAt: lead!.consentAt ? lead!.consentAt.toISOString() : new Date().toISOString(),
      createdAt: lead!.createdAt.toISOString()
    };
  }

  async getLeadsByTenant(tenantId: string, limit = 50): Promise<LegacyLead[]> {
    const rows = await this.db
      .select()
      .from(leads)
      .where(eq(leads.tenantId, tenantId))
      .orderBy(desc(leads.createdAt))
      .limit(limit);

    return rows.map((r) => ({
      id: r.id,
      tenantId: r.tenantId,
      sessionId: r.sessionId ?? '',
      name: r.name,
      email: r.email,
      phone: r.phone,
      companyUrl: r.companyUrl,
      notes: r.notes,
      consentAt: r.consentAt ? r.consentAt.toISOString() : new Date().toISOString(),
      createdAt: r.createdAt.toISOString()
    }));
  }
}

export class SubscriptionRepository {
  constructor(private db: Database) {}

  async upsertSubscription(input: {
    id?: string;
    tenantId: string;
    sessionId?: string | null;
    stripeCustomerId: string;
    stripeSubscriptionId?: string | null;
    stripeCheckoutId?: string | null;
    kind: 'subscription' | 'preview';
    status: string;
  }) {
    const [sub] = await this.db
      .insert(subscriptions)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        sessionId: input.sessionId,
        stripeCustomerId: input.stripeCustomerId,
        stripeSubscriptionId: input.stripeSubscriptionId,
        stripeCheckoutId: input.stripeCheckoutId,
        kind: input.kind,
        status: input.status
      })
      .onConflictDoUpdate({
        target: subscriptions.stripeSubscriptionId,
        set: {
          status: input.status
        }
      })
      .returning();
    return sub!;
  }

  async getByTenantId(tenantId: string) {
    return await this.db
      .select()
      .from(subscriptions)
      .where(eq(subscriptions.tenantId, tenantId))
      .orderBy(desc(subscriptions.createdAt));
  }
}

export class EvalRunRepository {
  constructor(private db: Database) {}

  async recordRun(input: {
    id?: string;
    tenantId: string;
    suite: string;
    passed: number;
    failed: number;
    detail: Record<string, unknown>;
  }) {
    const [run] = await this.db
      .insert(evalRuns)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        suite: input.suite,
        passed: input.passed,
        failed: input.failed,
        detail: input.detail
      })
      .returning();
    return run!;
  }

  async getRunsByTenant(tenantId: string, limit = 20) {
    return await this.db
      .select()
      .from(evalRuns)
      .where(eq(evalRuns.tenantId, tenantId))
      .orderBy(desc(evalRuns.createdAt))
      .limit(limit);
  }
}

export class UserRepository {
  constructor(private db: Database) {}

  async getById(userId: string) {
    const [user] = await this.db
      .select()
      .from(users)
      .where(eq(users.id, userId))
      .limit(1);
    return user ?? null;
  }

  async getByEmail(email: string) {
    const [user] = await this.db
      .select()
      .from(users)
      .where(eq(users.email, email.toLowerCase().trim()))
      .limit(1);
    return user ?? null;
  }

  async createUser(input: { id?: string; email: string; name?: string | null; passwordHash?: string | null }) {
    const [user] = await this.db
      .insert(users)
      .values({
        id: input.id,
        email: input.email.toLowerCase().trim(),
        name: input.name,
        passwordHash: input.passwordHash
      })
      .returning();
    return user!;
  }
}

export class MembershipRepository {
  constructor(private db: Database) {}

  async addMembership(input: {
    id?: string;
    tenantId: string;
    userId: string;
    role: UserRole;
  }) {
    const [membership] = await this.db
      .insert(memberships)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        userId: input.userId,
        role: input.role
      })
      .returning();
    return membership!;
  }

  async getMembership(tenantId: string, userId: string) {
    const [membership] = await this.db
      .select()
      .from(memberships)
      .where(and(eq(memberships.tenantId, tenantId), eq(memberships.userId, userId)))
      .limit(1);
    return membership ?? null;
  }

  async listMembersByTenant(tenantId: string) {
    return await this.db
      .select()
      .from(memberships)
      .where(eq(memberships.tenantId, tenantId));
  }
}

// ==========================================
// COMMERCIAL DOMAIN REPOSITORIES (M2)
// ==========================================

export class ChannelRepository {
  constructor(private db: Database) {}

  async createChannel(input: {
    id?: string;
    tenantId: string;
    type?: ChannelType;
    wabaId?: string | null;
    phoneNumberId?: string | null;
    displayNumber?: string | null;
    status?: string;
    tokenRef?: string | null;
    config?: Record<string, unknown>;
  }) {
    const [channel] = await this.db
      .insert(channels)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        type: input.type ?? 'whatsapp',
        wabaId: input.wabaId,
        phoneNumberId: input.phoneNumberId,
        displayNumber: input.displayNumber,
        status: input.status ?? 'active',
        tokenRef: input.tokenRef,
        config: input.config ?? {}
      })
      .returning();
    return channel!;
  }

  async getChannelByPhoneNumberId(phoneNumberId: string, tenantId?: string) {
    const conditions = [eq(channels.phoneNumberId, phoneNumberId)];
    if (tenantId) conditions.push(eq(channels.tenantId, tenantId));
    const [channel] = await this.db
      .select()
      .from(channels)
      .where(and(...conditions))
      .limit(1);
    return channel ?? null;
  }

  async listChannelsByTenant(tenantId: string) {
    return await this.db
      .select()
      .from(channels)
      .where(eq(channels.tenantId, tenantId));
  }
}

export class ContactRepository {
  constructor(private db: Database) {}

  async upsertContact(input: {
    id?: string;
    tenantId: string;
    waId?: string | null;
    displayName?: string | null;
    phoneE164?: string | null;
    language?: string;
    tags?: string[];
    consentSource?: string | null;
    consentAt?: Date | null;
  }) {
    const [contact] = await this.db
      .insert(contacts)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        waId: input.waId,
        displayName: input.displayName,
        phoneE164: input.phoneE164,
        language: input.language ?? 'de',
        tags: input.tags ?? [],
        consentSource: input.consentSource,
        consentAt: input.consentAt
      })
      .returning();
    return contact!;
  }

  async getContactByWaId(tenantId: string, waId: string) {
    const [contact] = await this.db
      .select()
      .from(contacts)
      .where(and(eq(contacts.tenantId, tenantId), eq(contacts.waId, waId)))
      .limit(1);
    return contact ?? null;
  }

  async getContactById(tenantId: string, contactId: string) {
    const [contact] = await this.db
      .select()
      .from(contacts)
      .where(and(eq(contacts.tenantId, tenantId), eq(contacts.id, contactId)))
      .limit(1);
    return contact ?? null;
  }
}

export class ConversationRepository {
  constructor(private db: Database) {}

  async createConversation(input: {
    id?: string;
    tenantId: string;
    channelId: string;
    contactId: string;
    status?: ConversationStatus;
    aiMode?: AiMode;
    serviceWindowExpiresAt?: Date | null;
  }) {
    const [conv] = await this.db
      .insert(conversations)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        channelId: input.channelId,
        contactId: input.contactId,
        status: input.status ?? 'open',
        aiMode: input.aiMode ?? 'suggest',
        serviceWindowExpiresAt: input.serviceWindowExpiresAt
      })
      .returning();
    return conv!;
  }

  async getOpenConversationByContact(tenantId: string, contactId: string) {
    const [conv] = await this.db
      .select()
      .from(conversations)
      .where(
        and(
          eq(conversations.tenantId, tenantId),
          eq(conversations.contactId, contactId),
          eq(conversations.status, 'open')
        )
      )
      .orderBy(desc(conversations.lastMessageAt))
      .limit(1);
    return conv ?? null;
  }

  async updateServiceWindow(conversationId: string, expiresAt: Date, tenantId?: string) {
    const conditions = [eq(conversations.id, conversationId)];
    if (tenantId) conditions.push(eq(conversations.tenantId, tenantId));
    const [conv] = await this.db
      .update(conversations)
      .set({ serviceWindowExpiresAt: expiresAt, lastMessageAt: new Date() })
      .where(and(...conditions))
      .returning();
    return conv ?? null;
  }

  async updateAiMode(conversationId: string, aiMode: AiMode, tenantId?: string) {
    const conditions = [eq(conversations.id, conversationId)];
    if (tenantId) conditions.push(eq(conversations.tenantId, tenantId));
    const [conv] = await this.db
      .update(conversations)
      .set({ aiMode })
      .where(and(...conditions))
      .returning();
    return conv ?? null;
  }
}

export class CommercialMessageRepository {
  constructor(private db: Database) {}

  async addMessage(input: {
    id?: string;
    tenantId: string;
    conversationId: string;
    direction: MessageDirection;
    wamid?: string | null;
    type?: MessageType;
    body?: string | null;
    mediaUrl?: string | null;
    billingCategory?: MessageBillingCategory;
    costEstimateMinor?: number;
    author?: string;
    rawPayload?: Record<string, unknown> | null;
  }) {
    const [msg] = await this.db
      .insert(messages)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        conversationId: input.conversationId,
        direction: input.direction,
        wamid: input.wamid,
        type: input.type ?? 'text',
        body: input.body,
        mediaUrl: input.mediaUrl,
        billingCategory: input.billingCategory ?? 'service',
        costEstimateMinor: input.costEstimateMinor ?? 0,
        author: input.author ?? 'agent',
        rawPayload: input.rawPayload
      })
      .returning();
    return msg!;
  }

  async getMessageByWamid(wamid: string, tenantId?: string) {
    const conditions = [eq(messages.wamid, wamid)];
    if (tenantId) conditions.push(eq(messages.tenantId, tenantId));
    const [msg] = await this.db
      .select()
      .from(messages)
      .where(and(...conditions))
      .limit(1);
    return msg ?? null;
  }

  async listMessagesByConversation(tenantId: string, conversationId: string, limit = 50) {
    return await this.db
      .select()
      .from(messages)
      .where(and(eq(messages.tenantId, tenantId), eq(messages.conversationId, conversationId)))
      .orderBy(desc(messages.createdAt))
      .limit(limit);
  }
}

export class CommercialLeadRepository {
  constructor(private db: Database) {}

  async createLead(input: {
    id?: string;
    tenantId: string;
    contactId: string;
    conversationId?: string | null;
    leadType?: LeadType;
    state?: LeadState;
    score?: number;
    valueEstimateMinor?: number;
    currency?: string;
  }) {
    const [lead] = await this.db
      .insert(leads)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        contactId: input.contactId,
        conversationId: input.conversationId,
        leadType: input.leadType ?? 'quote_request',
        state: input.state ?? 'new',
        score: input.score ?? 50,
        valueEstimateMinor: input.valueEstimateMinor ?? 0,
        currency: input.currency ?? 'CHF'
      })
      .returning();
    return lead!;
  }

  async updateLeadState(tenantId: string, leadId: string, state: LeadState) {
    const [lead] = await this.db
      .update(leads)
      .set({ state, updatedAt: new Date() })
      .where(and(eq(leads.tenantId, tenantId), eq(leads.id, leadId)))
      .returning();
    return lead ?? null;
  }

  async getLeadById(tenantId: string, leadId: string) {
    const [lead] = await this.db
      .select()
      .from(leads)
      .where(and(eq(leads.tenantId, tenantId), eq(leads.id, leadId)))
      .limit(1);
    return lead ?? null;
  }

  async listLeadsByTenant(tenantId: string, state?: LeadState) {
    const conditions = [eq(leads.tenantId, tenantId)];
    if (state) conditions.push(eq(leads.state, state));
    return await this.db
      .select()
      .from(leads)
      .where(and(...conditions))
      .orderBy(desc(leads.createdAt));
  }
}

export class OfferingRepository {
  constructor(private db: Database) {}

  async upsertOffering(input: {
    id?: string;
    tenantId: string;
    sku: string;
    name: string;
    description?: string | null;
    priceType?: PriceType;
    priceMinor: number;
    currency?: string;
    serviceArea?: string | null;
    durationMinutes?: number | null;
    active?: boolean;
    attributes?: Record<string, unknown>;
  }) {
    const [offering] = await this.db
      .insert(offerings)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        sku: input.sku,
        name: input.name,
        description: input.description,
        priceType: input.priceType ?? 'fixed',
        priceMinor: input.priceMinor,
        currency: input.currency ?? 'CHF',
        serviceArea: input.serviceArea,
        durationMinutes: input.durationMinutes,
        active: input.active ?? true,
        attributes: input.attributes ?? {}
      })
      .returning();
    return offering!;
  }

  async getOfferingBySku(tenantId: string, sku: string) {
    const [offering] = await this.db
      .select()
      .from(offerings)
      .where(and(eq(offerings.tenantId, tenantId), eq(offerings.sku, sku)))
      .limit(1);
    return offering ?? null;
  }

  async listActiveOfferings(tenantId: string) {
    return await this.db
      .select()
      .from(offerings)
      .where(and(eq(offerings.tenantId, tenantId), eq(offerings.active, true)));
  }
}

export class QuoteRequestRepository {
  constructor(private db: Database) {}

  async createQuoteRequest(input: {
    id?: string;
    tenantId: string;
    leadId: string;
    fields?: QuoteRequestFields;
    completeness?: number;
    missingFields?: string[];
    suggestedPackage?: string | null;
  }) {
    const [qr] = await this.db
      .insert(quoteRequests)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        leadId: input.leadId,
        fields: input.fields ?? {},
        completeness: input.completeness ?? 0.0,
        missingFields: input.missingFields ?? [],
        suggestedPackage: input.suggestedPackage
      })
      .returning();
    return qr!;
  }

  async getQuoteRequestByLead(tenantId: string, leadId: string) {
    const [qr] = await this.db
      .select()
      .from(quoteRequests)
      .where(and(eq(quoteRequests.tenantId, tenantId), eq(quoteRequests.leadId, leadId)))
      .limit(1);
    return qr ?? null;
  }
}

export class OrderRepository {
  constructor(private db: Database) {}

  async createOrder(input: {
    id?: string;
    tenantId: string;
    leadId: string;
    contactId: string;
    lineItems?: OrderLineItem[];
    status?: OrderStatus;
    amountMinor?: number;
    currency?: string;
    stripePaymentIntentId?: string | null;
    stripeCheckoutId?: string | null;
  }) {
    const [order] = await this.db
      .insert(orders)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        leadId: input.leadId,
        contactId: input.contactId,
        lineItems: input.lineItems ?? [],
        status: input.status ?? 'draft',
        amountMinor: input.amountMinor ?? 0,
        currency: input.currency ?? 'CHF',
        stripePaymentIntentId: input.stripePaymentIntentId,
        stripeCheckoutId: input.stripeCheckoutId
      })
      .returning();
    return order!;
  }

  async updateOrderStatus(tenantId: string, orderId: string, status: OrderStatus) {
    const [order] = await this.db
      .update(orders)
      .set({ status, updatedAt: new Date() })
      .where(and(eq(orders.tenantId, tenantId), eq(orders.id, orderId)))
      .returning();
    return order ?? null;
  }

  async getOrderById(tenantId: string, orderId: string) {
    const [order] = await this.db
      .select()
      .from(orders)
      .where(and(eq(orders.tenantId, tenantId), eq(orders.id, orderId)))
      .limit(1);
    return order ?? null;
  }
}

export class PaymentRepository {
  constructor(private db: Database) {}

  async recordPayment(input: {
    id?: string;
    tenantId: string;
    orderId: string;
    stripePaymentIntentId: string;
    amountMinor: number;
    currency?: string;
    status?: 'succeeded' | 'refunded' | 'failed';
  }) {
    const [payment] = await this.db
      .insert(payments)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        orderId: input.orderId,
        stripePaymentIntentId: input.stripePaymentIntentId,
        amountMinor: input.amountMinor,
        currency: input.currency ?? 'CHF',
        status: input.status ?? 'succeeded'
      })
      .returning();
    return payment!;
  }
}

export class TimelineEventRepository {
  constructor(private db: Database) {}

  async recordEvent(input: {
    id?: string;
    tenantId: string;
    aggregateType: string;
    aggregateId: string;
    eventType: string;
    payload?: Record<string, unknown>;
  }) {
    const [evt] = await this.db
      .insert(timelineEvents)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        aggregateType: input.aggregateType,
        aggregateId: input.aggregateId,
        eventType: input.eventType,
        payload: input.payload ?? {}
      })
      .returning();
    return evt!;
  }

  async listEventsByAggregate(tenantId: string, aggregateType: string, aggregateId: string) {
    return await this.db
      .select()
      .from(timelineEvents)
      .where(
        and(
          eq(timelineEvents.tenantId, tenantId),
          eq(timelineEvents.aggregateType, aggregateType),
          eq(timelineEvents.aggregateId, aggregateId)
        )
      )
      .orderBy(desc(timelineEvents.createdAt));
  }
}

export class AiRunRepository {
  constructor(private db: Database) {}

  async recordAiRun(input: {
    id?: string;
    tenantId: string;
    conversationId: string;
    messageId?: string | null;
    model: string;
    inputTokens?: number;
    outputTokens?: number;
    latencyMs?: number;
    promptRef?: string | null;
    outcome?: AiRunOutcome;
  }) {
    const [run] = await this.db
      .insert(aiRuns)
      .values({
        id: input.id,
        tenantId: input.tenantId,
        conversationId: input.conversationId,
        messageId: input.messageId,
        model: input.model,
        inputTokens: input.inputTokens ?? 0,
        outputTokens: input.outputTokens ?? 0,
        latencyMs: input.latencyMs ?? 0,
        promptRef: input.promptRef,
        outcome: input.outcome ?? 'drafted'
      })
      .returning();
    return run!;
  }

  async listAiRunsByTenant(tenantId: string, limit = 100) {
    return await this.db
      .select()
      .from(aiRuns)
      .where(eq(aiRuns.tenantId, tenantId))
      .orderBy(desc(aiRuns.createdAt))
      .limit(limit);
  }
}



