import type { Tier } from '@salesops/types';

export interface DailyUsagePoint {
  date: string; // "YYYY-MM-DD"
  conversations: number;
}

export interface DepletionForecast {
  dailyBurnRate: number; // 7-day rolling average
  daysRemainingInPeriod: number;
  projectedTotalConversations: number;
  projectedExhaustionDate: string | null;
  willExhaustBeforePeriodEnd: boolean;
}

export type RecommendationType =
  | 'maintain'
  | 'buy_blocks'
  | 'upgrade_tier'
  | 'downgrade_tier';

export interface RecommendationOption {
  name: string;
  costEur: number;
  details: string;
}

export interface PlanRecommendation {
  type: RecommendationType;
  headline: string;
  explanation: string;
  breakdown: {
    optionA: RecommendationOption;
    optionB?: RecommendationOption;
    recommendedOption: string;
    estimatedSavingsEur?: number;
  };
}

export const TIER_DETAILS: Record<Tier, { name: string; priceEur: number; included: number; nextTier?: Tier; prevTier?: Tier }> = {
  lite: { name: 'Sales Ops Lite', priceEur: 29, included: 100, nextTier: 'standard' },
  standard: { name: 'Sales Ops Standard', priceEur: 79, included: 500, nextTier: 'europe', prevTier: 'lite' },
  europe: { name: 'Sales Ops Europe (EU AI Act & Data Residency)', priceEur: 99, included: 500, nextTier: 'premium', prevTier: 'standard' },
  premium: { name: 'Sales Ops Premium', priceEur: 199, included: 2000, prevTier: 'europe' },
  custom: { name: 'Sales Ops Enterprise', priceEur: 499, included: 10000 }
};

export const TOP_UP_BLOCK_SIZE = 100;
export const TOP_UP_BLOCK_PRICE_EUR = 15; // 15€ per 100 conversations

export function calculateDepletionForecast(
  history: DailyUsagePoint[],
  entitlement: {
    includedConversations: number;
    periodEnd: Date;
    currentUsage: number;
  },
  now: Date = new Date()
): DepletionForecast {
  // 1. Calculate 7-day average daily burn rate
  const recentDays = history.slice(-7);
  const totalInRecent = recentDays.reduce((acc, p) => acc + p.conversations, 0);
  const dailyBurnRate = recentDays.length > 0 ? totalInRecent / recentDays.length : 0;

  // 2. Days remaining in current billing period
  const msRemaining = Math.max(0, entitlement.periodEnd.getTime() - now.getTime());
  const daysRemainingInPeriod = Math.max(1, Math.ceil(msRemaining / (1000 * 60 * 60 * 24)));

  // 3. Projected usage by period end
  const projectedRemainingUsage = Math.round(dailyBurnRate * daysRemainingInPeriod);
  const projectedTotalConversations = entitlement.currentUsage + projectedRemainingUsage;

  // 4. Projected exhaustion date
  const remainingIncluded = Math.max(0, entitlement.includedConversations - entitlement.currentUsage);
  let projectedExhaustionDate: string | null = null;
  let willExhaustBeforePeriodEnd = false;

  if (dailyBurnRate > 0 && remainingIncluded > 0) {
    const daysUntilExhaustion = remainingIncluded / dailyBurnRate;
    if (daysUntilExhaustion < daysRemainingInPeriod) {
      willExhaustBeforePeriodEnd = true;
      const exhaustTime = now.getTime() + daysUntilExhaustion * 24 * 60 * 60 * 1000;
      projectedExhaustionDate = new Date(exhaustTime).toISOString().slice(0, 10);
    }
  } else if (remainingIncluded === 0) {
    willExhaustBeforePeriodEnd = true;
    projectedExhaustionDate = now.toISOString().slice(0, 10);
  }

  return {
    dailyBurnRate: Math.round(dailyBurnRate * 10) / 10,
    daysRemainingInPeriod,
    projectedTotalConversations,
    projectedExhaustionDate,
    willExhaustBeforePeriodEnd
  };
}

export function calculateHonestRecommendation(options: {
  currentTier: Tier;
  currentUsage: number;
  includedConversations: number;
  forecast: DepletionForecast;
  trailingCyclesUsagePercent?: number[]; // Usage percent for past 3 periods (e.g. [25, 30, 28])
  locale?: string;
}): PlanRecommendation {
  const { currentTier, currentUsage, includedConversations, forecast, trailingCyclesUsagePercent = [], locale = 'pt-PT' } = options;
  const currentTierInfo = TIER_DETAILS[currentTier] || TIER_DETAILS.standard;

  // 1. Check for Downgrade Recommendation (Rule: 3 consecutive cycles under 40% usage)
  if (
    trailingCyclesUsagePercent.length >= 3 &&
    trailingCyclesUsagePercent.every((pct) => pct < 40) &&
    currentTierInfo.prevTier
  ) {
    const prevTierInfo = TIER_DETAILS[currentTierInfo.prevTier];
    const monthlySavings = currentTierInfo.priceEur - prevTierInfo.priceEur;

    return {
      type: 'downgrade_tier',
      headline: locale.startsWith('en')
        ? `Save €${monthlySavings}/month with a plan downgrade`
        : `Poupe ${monthlySavings}€/mês com a redução do seu plano`,
      explanation: locale.startsWith('en')
        ? `You have used under 40% of your plan capacity for 3 consecutive months. Downgrading to ${prevTierInfo.name} will save you €${monthlySavings} every month without affecting performance.`
        : `A sua loja utilizou menos de 40% da capacidade do plano durante 3 meses consecutivos. Mudar para o plano ${prevTierInfo.name} poupa-lhe ${monthlySavings}€ todos os meses sem comprometer o serviço.`,
      breakdown: {
        optionA: {
          name: prevTierInfo.name,
          costEur: prevTierInfo.priceEur,
          details: `${prevTierInfo.included} conversações incluídas (${prevTierInfo.priceEur}€/mês)`
        },
        optionB: {
          name: currentTierInfo.name,
          costEur: currentTierInfo.priceEur,
          details: `${currentTierInfo.included} conversações incluídas (${currentTierInfo.priceEur}€/mês)`
        },
        recommendedOption: prevTierInfo.name,
        estimatedSavingsEur: monthlySavings
      }
    };
  }

  // 2. Check for Capacity Shortfall (Forecast projects exhaustion before period end)
  if (forecast.willExhaustBeforePeriodEnd && currentTierInfo.nextTier) {
    const projectedDeficit = Math.max(0, forecast.projectedTotalConversations - includedConversations);
    const blocksNeeded = Math.ceil(projectedDeficit / TOP_UP_BLOCK_SIZE);
    const topUpCostEur = blocksNeeded * TOP_UP_BLOCK_PRICE_EUR;

    const nextTierInfo = TIER_DETAILS[currentTierInfo.nextTier];
    const upgradeDeltaEur = nextTierInfo.priceEur - currentTierInfo.priceEur;

    if (topUpCostEur < upgradeDeltaEur) {
      // Top-up blocks is the honest cheapest path
      return {
        type: 'buy_blocks',
        headline: locale.startsWith('en')
          ? `Top-up recommendation: Add ${blocksNeeded * TOP_UP_BLOCK_SIZE} conversations for €${topUpCostEur}`
          : `Recomendação mais económica: Adicionar pacote de ${blocksNeeded * TOP_UP_BLOCK_SIZE} conversações (${topUpCostEur}€)`,
        explanation: locale.startsWith('en')
          ? `At your current rate of ${forecast.dailyBurnRate} conv/day, you need ~${projectedDeficit} more conversations. Buying top-up blocks (€${topUpCostEur}) is cheaper than upgrading to ${nextTierInfo.name} (+€${upgradeDeltaEur}).`
          : `Ao ritmo atual de ${forecast.dailyBurnRate} conversações/dia, precisará de cerca de ${projectedDeficit} conversações adicionais. Comprar pacotes avulso (${topUpCostEur}€) é mais barato do que atualizar para o plano ${nextTierInfo.name} (+${upgradeDeltaEur}€).`,
        breakdown: {
          optionA: {
            name: `${blocksNeeded}x Pacote Top-up (+${blocksNeeded * TOP_UP_BLOCK_SIZE} conversações)`,
            costEur: topUpCostEur,
            details: `${blocksNeeded * TOP_UP_BLOCK_SIZE} conversações adicionais válidas até ao final do período (${topUpCostEur}€)`
          },
          optionB: {
            name: `Upgrade para ${nextTierInfo.name}`,
            costEur: upgradeDeltaEur,
            details: `${nextTierInfo.included} conversações incluídas (+${upgradeDeltaEur}€/mês)`
          },
          recommendedOption: `${blocksNeeded}x Pacote Top-up`,
          estimatedSavingsEur: upgradeDeltaEur - topUpCostEur
        }
      };
    }

    // Upgrade is cheaper
    return {
      type: 'upgrade_tier',
      headline: locale.startsWith('en')
        ? `Upgrade recommendation: Move to ${nextTierInfo.name} to save on high volume`
        : `Recomendação: Mudar para o plano ${nextTierInfo.name}`,
      explanation: locale.startsWith('en')
        ? `Your store is growing rapidly. Upgrading to ${nextTierInfo.name} (+€${upgradeDeltaEur}/mo) is cheaper than paying for ${blocksNeeded} top-up blocks (€${topUpCostEur}).`
        : `O volume da sua loja está a crescer rapidamente. Mudar para o plano ${nextTierInfo.name} (+${upgradeDeltaEur}€/mês) é mais vantajoso do que comprar ${blocksNeeded} pacotes avulso (${topUpCostEur}€).`,
      breakdown: {
        optionA: {
          name: `Upgrade para ${nextTierInfo.name}`,
          costEur: upgradeDeltaEur,
          details: `${nextTierInfo.included} conversações/mês (+${upgradeDeltaEur}€)`
        },
        optionB: {
          name: `${blocksNeeded}x Pacotes Top-up`,
          costEur: topUpCostEur,
          details: `${blocksNeeded * TOP_UP_BLOCK_SIZE} conversações adicionais (${topUpCostEur}€)`
        },
        recommendedOption: `Upgrade para ${nextTierInfo.name}`,
        estimatedSavingsEur: topUpCostEur - upgradeDeltaEur
      }
    };
  }

  // 3. Steady State: Maintain Current Plan
  return {
    type: 'maintain',
    headline: locale.startsWith('en')
      ? 'Your current plan is optimal'
      : 'O seu plano atual está calibrado e otimizado',
    explanation: locale.startsWith('en')
      ? `You have used ${currentUsage} of ${includedConversations} conversations (${Math.round((currentUsage / includedConversations) * 100)}%). Your projected usage will stay well within your plan allowance.`
      : `Utilizou ${currentUsage} de ${includedConversations} conversações (${Math.round((currentUsage / includedConversations) * 100)}%). A projeção indica que o seu consumo se manterá confortavelmente dentro do plano.`,
    breakdown: {
      optionA: {
        name: currentTierInfo.name,
        costEur: currentTierInfo.priceEur,
        details: `${includedConversations} conversações incluídas (${currentTierInfo.priceEur}€/mês)`
      },
      recommendedOption: currentTierInfo.name
    }
  };
}
