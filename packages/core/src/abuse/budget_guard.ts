import type { TenantConfig } from '@salesops/types';
import type { AbuseCheckResult } from './types.js';
import { buildDegradedMessage } from './degradation.js';

export interface BudgetGuardContext {
  tenantConfig: TenantConfig;
  sessionTokensUsed: number;
  monthlySpendMinor?: number;
  locale?: string;
}

export class SessionBudgetGuard {
  check(ctx: BudgetGuardContext): AbuseCheckResult {
    const tokenBudget = ctx.tenantConfig.limits?.tokenBudgetPerSession ?? 40000;
    const monthlySpendCapEur = ctx.tenantConfig.limits?.monthlySpendCapEur ?? 25;
    const monthlySpendCapMinor = monthlySpendCapEur * 100;
    const monthlySpendMinor = ctx.monthlySpendMinor ?? 0;

    // 1. Check Session Token Budget
    if (ctx.sessionTokensUsed >= tokenBudget) {
      const fallback = buildDegradedMessage({
        tenantName: ctx.tenantConfig.displayName,
        locale: ctx.locale,
        storePolicy: ctx.tenantConfig.policy,
        escalationContact: ctx.tenantConfig.policy.contact.humanEscalation,
        reason: 'token_budget_exceeded'
      });

      return {
        allowed: false,
        reason: 'token_budget_exceeded',
        degradeAction: 'static_faq_handoff',
        fallbackMessage: fallback,
        sessionTokensUsed: ctx.sessionTokensUsed,
        sessionTokenBudget: tokenBudget,
        monthlySpendMinor,
        monthlySpendCapMinor
      };
    }

    // 2. Check Monthly Spend Cap
    if (monthlySpendMinor >= monthlySpendCapMinor) {
      const fallback = buildDegradedMessage({
        tenantName: ctx.tenantConfig.displayName,
        locale: ctx.locale,
        storePolicy: ctx.tenantConfig.policy,
        escalationContact: ctx.tenantConfig.policy.contact.humanEscalation,
        reason: 'monthly_spend_cap_exceeded'
      });

      return {
        allowed: false,
        reason: 'monthly_spend_cap_exceeded',
        degradeAction: 'static_faq_handoff',
        fallbackMessage: fallback,
        sessionTokensUsed: ctx.sessionTokensUsed,
        sessionTokenBudget: tokenBudget,
        monthlySpendMinor,
        monthlySpendCapMinor
      };
    }

    return {
      allowed: true,
      sessionTokensUsed: ctx.sessionTokensUsed,
      sessionTokenBudget: tokenBudget,
      monthlySpendMinor,
      monthlySpendCapMinor
    };
  }
}

export const defaultBudgetGuard = new SessionBudgetGuard();
