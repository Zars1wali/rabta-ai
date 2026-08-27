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
  evalRuns
} from './schema.js';
import type {
  TenantConfig,
  Catalog,
  CatalogItem,
  AgentMessage,
  Lead,
  FunnelStage
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
      role: r.role as AgentMessage['role'],
      content: r.content ?? '',
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
  }): Promise<Lead> {
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
      sessionId: lead!.sessionId,
      name: lead!.name,
      email: lead!.email,
      phone: lead!.phone,
      companyUrl: lead!.companyUrl,
      notes: lead!.notes,
      consentAt: lead!.consentAt.toISOString(),
      createdAt: lead!.createdAt.toISOString()
    };
  }

  async getLeadsByTenant(tenantId: string, limit = 50): Promise<Lead[]> {
    const rows = await this.db
      .select()
      .from(leads)
      .where(eq(leads.tenantId, tenantId))
      .orderBy(desc(leads.createdAt))
      .limit(limit);

    return rows.map((r) => ({
      id: r.id,
      tenantId: r.tenantId,
      sessionId: r.sessionId,
      name: r.name,
      email: r.email,
      phone: r.phone,
      companyUrl: r.companyUrl,
      notes: r.notes,
      consentAt: r.consentAt.toISOString(),
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

