import { eq, and, lte, gte, sql } from 'drizzle-orm';
import type { Database } from '../db/client.js';
import {
  entitlements,
  usageEvents,
  usageCounters,
  depletionAlerts
} from '../db/schema.js';
import type {
  EntitlementRecord,
  UsageCounterRecord,
  UsageEventRecord
} from './types.js';

export class MeteringRepository {
  constructor(private db: Database) {}

  async getActiveEntitlement(tenantId: string, now: Date = new Date()): Promise<EntitlementRecord | null> {
    const rows = await this.db
      .select()
      .from(entitlements)
      .where(
        and(
          eq(entitlements.tenantId, tenantId),
          eq(entitlements.status, 'active'),
          lte(entitlements.periodStart, now),
          gte(entitlements.periodEnd, now)
        )
      )
      .limit(1);

    if (!rows[0]) return null;
    const r = rows[0];
    return {
      id: r.id,
      tenantId: r.tenantId,
      periodStart: r.periodStart,
      periodEnd: r.periodEnd,
      includedConversations: r.includedConversations,
      overageRateMinor: r.overageRateMinor,
      overageCapMinor: r.overageCapMinor,
      status: r.status as 'active' | 'expired'
    };
  }

  async findActiveWindow(
    tenantId: string,
    identityHash: string,
    now: Date = new Date()
  ): Promise<UsageEventRecord | null> {
    const rows = await this.db
      .select()
      .from(usageEvents)
      .where(
        and(
          eq(usageEvents.tenantId, tenantId),
          eq(usageEvents.identityHash, identityHash),
          lte(usageEvents.windowStart, now),
          gte(usageEvents.windowEnd, now)
        )
      )
      .orderBy(sql`${usageEvents.windowEnd} DESC`)
      .limit(1);

    if (!rows[0]) return null;
    const r = rows[0];
    return {
      id: r.id,
      tenantId: r.tenantId,
      windowId: r.windowId,
      identityHash: r.identityHash,
      channel: r.channel,
      windowStart: r.windowStart,
      windowEnd: r.windowEnd,
      firstSeenAt: r.firstSeenAt
    };
  }

  async openUsageWindow(event: {
    tenantId: string;
    windowId: string;
    identityHash: string;
    channel: string;
    windowStart: Date;
    windowEnd: Date;
  }): Promise<UsageEventRecord> {
    const [row] = await this.db
      .insert(usageEvents)
      .values({
        tenantId: event.tenantId,
        windowId: event.windowId,
        identityHash: event.identityHash,
        channel: event.channel,
        windowStart: event.windowStart,
        windowEnd: event.windowEnd
      })
      .onConflictDoNothing()
      .returning();

    if (row) {
      return {
        id: row.id,
        tenantId: row.tenantId,
        windowId: row.windowId,
        identityHash: row.identityHash,
        channel: row.channel,
        windowStart: row.windowStart,
        windowEnd: row.windowEnd,
        firstSeenAt: row.firstSeenAt
      };
    }

    // If duplicate was inserted concurrently, return existing
    const existing = await this.findActiveWindow(event.tenantId, event.identityHash, event.windowStart);
    if (!existing) {
      throw new Error('Failed to record usage window');
    }
    return existing;
  }

  async incrementUsageCounter(
    tenantId: string,
    periodStart: Date,
    conversationsDelta = 0,
    tokensDelta = 0
  ): Promise<UsageCounterRecord> {
    const [row] = await this.db
      .insert(usageCounters)
      .values({
        tenantId,
        periodStart,
        conversationsUsed: conversationsDelta,
        tokensUsed: tokensDelta,
        lastEventAt: new Date(),
        updatedAt: new Date()
      })
      .onConflictDoUpdate({
        target: usageCounters.id,
        set: {
          conversationsUsed: sql`${usageCounters.conversationsUsed} + ${conversationsDelta}`,
          tokensUsed: sql`${usageCounters.tokensUsed} + ${tokensDelta}`,
          lastEventAt: new Date(),
          updatedAt: new Date()
        }
      })
      .returning();

    return {
      id: row!.id,
      tenantId: row!.tenantId,
      periodStart: row!.periodStart,
      conversationsUsed: row!.conversationsUsed,
      tokensUsed: row!.tokensUsed,
      lastEventAt: row!.lastEventAt,
      updatedAt: row!.updatedAt
    };
  }

  async getUsageCounter(tenantId: string, periodStart: Date): Promise<UsageCounterRecord | null> {
    const rows = await this.db
      .select()
      .from(usageCounters)
      .where(
        and(
          eq(usageCounters.tenantId, tenantId),
          eq(usageCounters.periodStart, periodStart)
        )
      )
      .limit(1);

    if (!rows[0]) return null;
    const r = rows[0];
    return {
      id: r.id,
      tenantId: r.tenantId,
      periodStart: r.periodStart,
      conversationsUsed: r.conversationsUsed,
      tokensUsed: r.tokensUsed,
      lastEventAt: r.lastEventAt,
      updatedAt: r.updatedAt
    };
  }

  async hasDepletionAlert(tenantId: string, periodStart: Date, threshold: number): Promise<boolean> {
    const rows = await this.db
      .select()
      .from(depletionAlerts)
      .where(
        and(
          eq(depletionAlerts.tenantId, tenantId),
          eq(depletionAlerts.periodStart, periodStart),
          eq(depletionAlerts.threshold, threshold)
        )
      )
      .limit(1);

    return rows.length > 0;
  }

  async recordDepletionAlert(
    tenantId: string,
    periodStart: Date,
    threshold: number,
    channel = 'email'
  ): Promise<void> {
    await this.db
      .insert(depletionAlerts)
      .values({
        tenantId,
        periodStart,
        threshold,
        channel
      })
      .onConflictDoNothing();
  }

  async reconcilePeriod(
    tenantId: string,
    periodStart: Date,
    periodEnd: Date
  ): Promise<{ reconciledConversations: number; drift: number }> {
    // Count exact distinct usage events in the period (source of truth)
    const countResult = await this.db
      .select({ count: sql<number>`count(*)::int` })
      .from(usageEvents)
      .where(
        and(
          eq(usageEvents.tenantId, tenantId),
          gte(usageEvents.firstSeenAt, periodStart),
          lte(usageEvents.firstSeenAt, periodEnd)
        )
      );

    const exactCount = countResult[0]?.count ?? 0;
    const currentCounter = await this.getUsageCounter(tenantId, periodStart);
    const cachedCount = currentCounter?.conversationsUsed ?? 0;
    const drift = exactCount - cachedCount;

    // Correct the cached counter
    await this.db
      .insert(usageCounters)
      .values({
        tenantId,
        periodStart,
        conversationsUsed: exactCount,
        tokensUsed: currentCounter?.tokensUsed ?? 0,
        lastEventAt: new Date(),
        updatedAt: new Date()
      })
      .onConflictDoUpdate({
        target: usageCounters.id,
        set: {
          conversationsUsed: exactCount,
          updatedAt: new Date()
        }
      });

    return {
      reconciledConversations: exactCount,
      drift
    };
  }
}
