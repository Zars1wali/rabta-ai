export type WhatsAppBillingCategory = 'service' | 'utility' | 'marketing' | 'authentication';

export interface ServiceWindowStatus {
  isOpen: boolean;
  expiresAt: Date;
  remainingMs: number;
  isExpiringSoon: boolean; // < 2 hours remaining
}

export interface MessageCostEstimate {
  category: WhatsAppBillingCategory;
  estimatedCostMinor: number; // in cents/rappen
  currency: string;
  isFreeTierEligible: boolean; // e.g. service conversations within free tier quota
}

export class ServiceWindowExpiredError extends Error {
  constructor(message = '24-hour customer service window has expired. Free-form messages are forbidden by Meta policy.') {
    super(message);
    this.name = 'ServiceWindowExpiredError';
  }
}

export class ServiceWindowEngine {
  private windowDurationMs: number;
  private expiringThresholdMs: number;

  constructor(windowDurationMs = 24 * 60 * 60 * 1000, expiringThresholdMs = 2 * 60 * 60 * 1000) {
    this.windowDurationMs = windowDurationMs;
    this.expiringThresholdMs = expiringThresholdMs;
  }

  calculateServiceWindow(lastInboundAt: Date, now: Date = new Date()): ServiceWindowStatus {
    const expiresAt = new Date(lastInboundAt.getTime() + this.windowDurationMs);
    const remainingMs = expiresAt.getTime() - now.getTime();
    const isOpen = remainingMs > 0;
    const isExpiringSoon = isOpen && remainingMs <= this.expiringThresholdMs;

    return {
      isOpen,
      expiresAt,
      remainingMs: Math.max(0, remainingMs),
      isExpiringSoon
    };
  }

  assertOutboundAllowed(lastInboundAt: Date | undefined | null, now: Date = new Date()): void {
    if (!lastInboundAt) {
      throw new ServiceWindowExpiredError('No recorded inbound message from customer. Outbound requires template message.');
    }
    const status = this.calculateServiceWindow(lastInboundAt, now);
    if (!status.isOpen) {
      throw new ServiceWindowExpiredError(`Customer service window expired at ${status.expiresAt.toISOString()}. Outbound requires approved Meta template.`);
    }
  }

  estimateMessageCost(
    category: WhatsAppBillingCategory,
    market: 'CH' | 'EU' | 'GLOBAL' = 'CH'
  ): MessageCostEstimate {
    // Meta Cloud API rates (estimates in CHF/EUR cents)
    const rateCard: Record<'CH' | 'EU' | 'GLOBAL', Record<WhatsAppBillingCategory, number>> = {
      CH: {
        service: 4,      // ~CHF 0.04
        utility: 3,      // ~CHF 0.03
        marketing: 8,    // ~CHF 0.08
        authentication: 4 // ~CHF 0.04
      },
      EU: {
        service: 3,      // ~€0.03
        utility: 3,      // ~€0.03
        marketing: 6,    // ~€0.06
        authentication: 3 // ~€0.03
      },
      GLOBAL: {
        service: 2,
        utility: 2,
        marketing: 5,
        authentication: 2
      }
    };

    const currency = market === 'CH' ? 'CHF' : 'EUR';
    const estimatedCostMinor = rateCard[market][category];
    const isFreeTierEligible = category === 'service';

    return {
      category,
      estimatedCostMinor,
      currency,
      isFreeTierEligible
    };
  }
}

export const defaultServiceWindowEngine = new ServiceWindowEngine();
