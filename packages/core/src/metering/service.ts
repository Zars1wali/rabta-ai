import type { MeteringRepository } from './repository.js';
import type { MeteringTurnResult } from './types.js';
import {
  computeIdentityHash,
  computeWindowBounds,
  computeWindowId
} from './identity.js';
import type { NotificationDispatcher } from '../notifications/types.js';

export interface MeteringServiceOptions {
  repo: MeteringRepository;
  hmacSecret?: string;
  notificationDispatcher?: NotificationDispatcher;
}

export interface TrackTurnOptions {
  tenantId: string;
  channel: string;
  visitorIdentifier: string;
  tokensUsed?: number;
  now?: Date;
}

export class MeteringService {
  private repo: MeteringRepository;
  private hmacSecret: string;
  private notificationDispatcher?: NotificationDispatcher;

  constructor(options: MeteringServiceOptions) {
    this.repo = options.repo;
    const secret = options.hmacSecret || process.env.METERING_HMAC_SECRET;
    if (!secret) {
      if (process.env.NODE_ENV === 'production') {
        throw new Error('METERING_HMAC_SECRET environment variable is required in production.');
      }
      this.hmacSecret = 'salesops_metering_secret_salt_2026';
    } else {
      this.hmacSecret = secret;
    }
    this.notificationDispatcher = options.notificationDispatcher;
  }

  async trackTurn(options: TrackTurnOptions): Promise<MeteringTurnResult> {
    const now = options.now || new Date();
    const identityHash = computeIdentityHash(this.hmacSecret, options.channel, options.visitorIdentifier);

    // 1. Check for active 24-hour service window
    const activeWindow = await this.repo.findActiveWindow(options.tenantId, identityHash, now);

    // 2. Fetch active entitlement for this billing period
    const entitlement = await this.repo.getActiveEntitlement(options.tenantId, now);
    const periodStart = entitlement?.periodStart || new Date(now.getFullYear(), now.getMonth(), 1);
    const included = entitlement?.includedConversations || 500;

    if (activeWindow) {
      // Existing active 24-hour window: no additional conversation billed
      if (options.tokensUsed && options.tokensUsed > 0) {
        await this.repo.incrementUsageCounter(options.tenantId, periodStart, 0, options.tokensUsed);
      }

      const counter = await this.repo.getUsageCounter(options.tenantId, periodStart);
      const used = counter?.conversationsUsed || 1;
      const percentUsed = Math.round((used / included) * 100);

      return {
        isNewWindow: false,
        windowId: activeWindow.windowId,
        identityHash,
        conversationsUsed: used,
        includedConversations: included,
        percentUsed
      };
    }

    // 3. New 24-hour window: opens billable conversation
    const { windowStart, windowEnd } = computeWindowBounds(now);
    const windowId = computeWindowId(options.tenantId, options.channel, identityHash, windowStart);

    await this.repo.openUsageWindow({
      tenantId: options.tenantId,
      windowId,
      identityHash,
      channel: options.channel,
      windowStart,
      windowEnd
    });

    // 4. Atomically increment billable conversation count
    const updatedCounter = await this.repo.incrementUsageCounter(
      options.tenantId,
      periodStart,
      1,
      options.tokensUsed || 0
    );

    const conversationsUsed = updatedCounter.conversationsUsed;
    const percentUsed = Math.round((conversationsUsed / included) * 100);

    // 5. Evaluate depletion alerts (80%, 100%, 120%)
    let alertTriggered: number | undefined;
    for (const threshold of [120, 100, 80]) {
      if (percentUsed >= threshold) {
        const alreadyAlerted = await this.repo.hasDepletionAlert(options.tenantId, periodStart, threshold);
        if (!alreadyAlerted) {
          await this.repo.recordDepletionAlert(options.tenantId, periodStart, threshold);
          alertTriggered = threshold;

          // Dispatch depletion alert notification if dispatcher provided
          if (this.notificationDispatcher) {
            await this.notificationDispatcher.dispatch({
              type: 'handoff_requested',
              tenantId: options.tenantId,
              sessionId: windowId,
              reason: `Alerta de Esgotamento de Plano: O seu plano atingiu ${threshold}% do limite de conversações incluídas (${conversationsUsed}/${included}).`
            });
          }
          break;
        }
      }
    }

    return {
      isNewWindow: true,
      windowId,
      identityHash,
      conversationsUsed,
      includedConversations: included,
      percentUsed,
      alertTriggered
    };
  }

  async reconcile(
    tenantId: string,
    periodStart: Date,
    periodEnd: Date
  ): Promise<{ reconciledConversations: number; drift: number }> {
    return await this.repo.reconcilePeriod(tenantId, periodStart, periodEnd);
  }
}
