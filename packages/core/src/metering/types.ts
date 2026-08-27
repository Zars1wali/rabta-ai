export interface EntitlementRecord {
  id: string;
  tenantId: string;
  periodStart: Date;
  periodEnd: Date;
  includedConversations: number;
  overageRateMinor: number;
  overageCapMinor: number;
  status: 'active' | 'expired';
}

export interface UsageEventRecord {
  id: string;
  tenantId: string;
  windowId: string;
  identityHash: string;
  channel: string;
  windowStart: Date;
  windowEnd: Date;
  firstSeenAt: Date;
}

export interface UsageCounterRecord {
  id: string;
  tenantId: string;
  periodStart: Date;
  conversationsUsed: number;
  tokensUsed: number;
  lastEventAt?: Date | null;
  updatedAt: Date;
}

export interface DepletionAlertRecord {
  id: string;
  tenantId: string;
  periodStart: Date;
  threshold: number; // 80, 100, 120
  triggeredAt: Date;
  channel: string;
}

export interface MeteringTurnResult {
  isNewWindow: boolean;
  windowId: string;
  identityHash: string;
  conversationsUsed: number;
  includedConversations: number;
  percentUsed: number;
  alertTriggered?: number;
}
