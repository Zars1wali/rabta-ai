import { describe, it, expect, vi } from 'vitest';
import {
  computeIdentityHash,
  computeWindowBounds,
  MeteringService
} from '../src/metering/index.js';
import type { MeteringRepository } from '../src/metering/repository.js';
import type { UsageEventRecord, UsageCounterRecord, EntitlementRecord } from '../src/metering/types.js';
import { REWILT_TENANT_ID } from '../src/db/seed.js';

describe('Metering & 24h Rolling Conversation Service Windows (WP-24 & WP-25)', () => {
  const tenantId = REWILT_TENANT_ID;
  const secret = 'test_metering_hmac_secret';

  it('computes deterministic HMAC-SHA256 identity hash', () => {
    const hash1 = computeIdentityHash(secret, 'web', 'visitor-ip-123.456');
    const hash2 = computeIdentityHash(secret, 'web', 'visitor-ip-123.456');
    const hash3 = computeIdentityHash(secret, 'whatsapp', 'visitor-ip-123.456');

    expect(hash1).toBe(hash2);
    expect(hash1).not.toBe(hash3); // Distinct by channel
    expect(hash1.length).toBe(64); // SHA-256 hex length
  });

  it('computes 24h window bounds starting from current time', () => {
    const now = new Date('2026-08-27T12:00:00Z');
    const { windowStart, windowEnd } = computeWindowBounds(now);
    expect(windowStart.toISOString()).toBe('2026-08-27T12:00:00.000Z');
    expect(windowEnd.toISOString()).toBe('2026-08-28T12:00:00.000Z');
  });

  it('deduplicates turns within 24h window (counts 1 conversation) and bills new window after 24h+1m', async () => {
    const activeWindows: UsageEventRecord[] = [];
    let conversationsCount = 0;
    let tokensCount = 0;

    const mockRepo = {
      getActiveEntitlement: vi.fn().mockResolvedValue({
        id: 'ent-1',
        tenantId,
        periodStart: new Date('2026-08-01T00:00:00Z'),
        periodEnd: new Date('2026-08-31T23:59:59Z'),
        includedConversations: 100,
        overageRateMinor: 10,
        overageCapMinor: 5000,
        status: 'active'
      } as EntitlementRecord),

      findActiveWindow: vi.fn().mockImplementation(async (_tId, identityHash, now: Date) => {
        return activeWindows.find(
          (w) => w.identityHash === identityHash && w.windowStart <= now && w.windowEnd >= now
        ) || null;
      }),

      openUsageWindow: vi.fn().mockImplementation(async (event) => {
        const row: UsageEventRecord = {
          id: `win-${activeWindows.length + 1}`,
          ...event,
          firstSeenAt: event.windowStart
        };
        activeWindows.push(row);
        return row;
      }),

      incrementUsageCounter: vi.fn().mockImplementation(async (_tId, periodStart, convDelta, tokDelta) => {
        conversationsCount += convDelta;
        tokensCount += tokDelta;
        return {
          id: 'cnt-1',
          tenantId,
          periodStart,
          conversationsUsed: conversationsCount,
          tokensUsed: tokensCount,
          updatedAt: new Date()
        } as UsageCounterRecord;
      }),

      getUsageCounter: vi.fn().mockImplementation(async () => {
        return {
          id: 'cnt-1',
          tenantId,
          periodStart: new Date('2026-08-01T00:00:00Z'),
          conversationsUsed: conversationsCount,
          tokensUsed: tokensCount,
          updatedAt: new Date()
        } as UsageCounterRecord;
      }),

      hasDepletionAlert: vi.fn().mockResolvedValue(false),
      recordDepletionAlert: vi.fn().mockResolvedValue(undefined)
    } as unknown as MeteringRepository;

    const meteringService = new MeteringService({ repo: mockRepo, hmacSecret: secret });

    // Turn 1: T0 (10:00) -> Opens Window 1
    const t0 = new Date('2026-08-27T10:00:00Z');
    const res1 = await meteringService.trackTurn({
      tenantId,
      channel: 'web',
      visitorIdentifier: 'user_session_abc',
      tokensUsed: 150,
      now: t0
    });

    expect(res1.isNewWindow).toBe(true);
    expect(res1.conversationsUsed).toBe(1);
    expect(conversationsCount).toBe(1);

    // Turn 2: T0 + 5 hours (15:00) -> Reuses Window 1 (Deduplicated, 0 new conversations)
    const t2 = new Date('2026-08-27T15:00:00Z');
    const res2 = await meteringService.trackTurn({
      tenantId,
      channel: 'web',
      visitorIdentifier: 'user_session_abc',
      tokensUsed: 200,
      now: t2
    });

    expect(res2.isNewWindow).toBe(false);
    expect(res2.windowId).toBe(res1.windowId);
    expect(res2.conversationsUsed).toBe(1);
    expect(conversationsCount).toBe(1); // STILL 1 conversation

    // Turn 3: T0 + 24 hours + 1 minute (Next day 10:01) -> Window 1 Expired -> Opens Window 2 (Billed as conversation #2)
    const t3 = new Date('2026-08-28T10:01:00Z');
    const res3 = await meteringService.trackTurn({
      tenantId,
      channel: 'web',
      visitorIdentifier: 'user_session_abc',
      tokensUsed: 100,
      now: t3
    });

    expect(res3.isNewWindow).toBe(true);
    expect(res3.windowId).not.toBe(res1.windowId);
    expect(res3.conversationsUsed).toBe(2);
    expect(conversationsCount).toBe(2);
  });

  it('triggers 80% and 100% depletion alerts exactly once per period', async () => {
    const triggeredThresholds: number[] = [];

    const mockRepo = {
      getActiveEntitlement: vi.fn().mockResolvedValue({
        id: 'ent-1',
        tenantId,
        periodStart: new Date('2026-08-01T00:00:00Z'),
        periodEnd: new Date('2026-08-31T23:59:59Z'),
        includedConversations: 10, // 10 conversations cap
        overageRateMinor: 10,
        overageCapMinor: 5000,
        status: 'active'
      } as EntitlementRecord),

      findActiveWindow: vi.fn().mockResolvedValue(null),
      openUsageWindow: vi.fn().mockResolvedValue({} as UsageEventRecord),
      incrementUsageCounter: vi.fn().mockResolvedValue({
        id: 'cnt-1',
        tenantId,
        periodStart: new Date('2026-08-01T00:00:00Z'),
        conversationsUsed: 8, // 8 / 10 = 80%!
        tokensUsed: 1000,
        updatedAt: new Date()
      } as UsageCounterRecord),

      hasDepletionAlert: vi.fn().mockImplementation(async (_tId, _pStart, threshold) => {
        return triggeredThresholds.includes(threshold);
      }),

      recordDepletionAlert: vi.fn().mockImplementation(async (_tId, _pStart, threshold) => {
        triggeredThresholds.push(threshold);
      })
    } as unknown as MeteringRepository;

    const mockDispatcher = {
      dispatch: vi.fn().mockResolvedValue({ sent: true, channel: 'email' })
    };

    const meteringService = new MeteringService({
      repo: mockRepo,
      hmacSecret: secret,
      notificationDispatcher: mockDispatcher
    });

    const res = await meteringService.trackTurn({
      tenantId,
      channel: 'web',
      visitorIdentifier: 'visitor_80_percent',
      tokensUsed: 100
    });

    expect(res.percentUsed).toBe(80);
    expect(res.alertTriggered).toBe(80);
    expect(triggeredThresholds).toContain(80);
    expect(mockDispatcher.dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'handoff_requested',
        reason: expect.stringContaining('80% do limite')
      })
    );
  });

  it('reconciles cached counter against immutable event stream correcting drift', async () => {
    const mockRepo = {
      reconcilePeriod: vi.fn().mockResolvedValue({
        reconciledConversations: 42,
        drift: 2 // Counter was 40, actual immutable events were 42
      })
    } as unknown as MeteringRepository;

    const meteringService = new MeteringService({ repo: mockRepo, hmacSecret: secret });

    const result = await meteringService.reconcile(
      tenantId,
      new Date('2026-08-01T00:00:00Z'),
      new Date('2026-08-31T23:59:59Z')
    );

    expect(result.reconciledConversations).toBe(42);
    expect(result.drift).toBe(2);
  });
});
