import type { StorePolicy } from '@salesops/types';

export type AbuseViolationReason =
  | 'token_budget_exceeded'
  | 'monthly_spend_cap_exceeded'
  | 'rate_limit_exceeded'
  | 'origin_forbidden';

export interface AbuseCheckResult {
  allowed: boolean;
  reason?: AbuseViolationReason;
  degradeAction?: 'static_faq_handoff' | 'throttle' | 'reject';
  fallbackMessage?: string;
  sessionTokensUsed: number;
  sessionTokenBudget: number;
  monthlySpendMinor: number;
  monthlySpendCapMinor: number;
}

export interface RateLimitCheckResult {
  allowed: boolean;
  remaining: number;
  resetMs: number;
}

export interface DegradedResponseOptions {
  tenantName: string;
  locale?: string;
  storePolicy?: StorePolicy;
  escalationContact?: string;
  reason?: AbuseViolationReason;
}
