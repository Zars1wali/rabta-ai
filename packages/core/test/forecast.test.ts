import { describe, it, expect } from 'vitest';
import {
  calculateDepletionForecast,
  calculateHonestRecommendation,
  type DailyUsagePoint
} from '../src/metering/index.js';

describe('Depletion Forecast & Honest Recommendation Engine (WP-27)', () => {
  it('calculates 7-day average burn rate and projected exhaustion date', () => {
    const history: DailyUsagePoint[] = [
      { date: '2026-08-20', conversations: 10 },
      { date: '2026-08-21', conversations: 12 },
      { date: '2026-08-22', conversations: 14 },
      { date: '2026-08-23', conversations: 10 },
      { date: '2026-08-24', conversations: 15 },
      { date: '2026-08-25', conversations: 11 },
      { date: '2026-08-26', conversations: 12 }
    ]; // Total = 84 / 7 = 12 convs/day

    const now = new Date('2026-08-27T00:00:00Z');
    const periodEnd = new Date('2026-08-31T23:59:59Z'); // 5 days remaining

    const forecast = calculateDepletionForecast(
      history,
      {
        includedConversations: 100,
        periodEnd,
        currentUsage: 80 // 20 remaining
      },
      now
    );

    expect(forecast.dailyBurnRate).toBe(12);
    expect(forecast.daysRemainingInPeriod).toBe(5);
    // At 12/day, 20 remaining lasts ~1.6 days -> exhausts before period end!
    expect(forecast.willExhaustBeforePeriodEnd).toBe(true);
    expect(forecast.projectedExhaustionDate).toBe('2026-08-28');
  });

  it('honestly recommends buying top-up blocks when cheaper than a full tier upgrade', () => {
    // Current tier: Standard (79€, 500 convs). Next tier: Europe (99€, +20€/mo).
    // Needs ~40 more conversations.
    // 1x Top-up block = 100 convs = 15€ < 20€ upgrade delta!
    const forecast = {
      dailyBurnRate: 20,
      daysRemainingInPeriod: 5,
      projectedTotalConversations: 540,
      projectedExhaustionDate: '2026-08-28',
      willExhaustBeforePeriodEnd: true
    };

    const recommendation = calculateHonestRecommendation({
      currentTier: 'standard',
      currentUsage: 480,
      includedConversations: 500,
      forecast
    });

    expect(recommendation.type).toBe('buy_blocks');
    expect(recommendation.breakdown.recommendedOption).toContain('1x Pacote Top-up');
    expect(recommendation.breakdown.optionA.costEur).toBe(15);
    expect(recommendation.breakdown.estimatedSavingsEur).toBe(5); // 20€ - 15€ = 5€ saved
  });

  it('honestly recommends plan upgrade when high deficit makes top-up blocks more expensive', () => {
    // Current tier: Standard (79€, 500 convs). Next tier: Europe (99€, +20€/mo).
    // Needs ~250 more conversations.
    // 3x Top-up blocks = 300 convs = 45€ > 20€ upgrade delta!
    const forecast = {
      dailyBurnRate: 60,
      daysRemainingInPeriod: 5,
      projectedTotalConversations: 750,
      projectedExhaustionDate: '2026-08-27',
      willExhaustBeforePeriodEnd: true
    };

    const recommendation = calculateHonestRecommendation({
      currentTier: 'standard',
      currentUsage: 490,
      includedConversations: 500,
      forecast
    });

    expect(recommendation.type).toBe('upgrade_tier');
    expect(recommendation.breakdown.recommendedOption).toContain('Upgrade para Sales Ops Europe');
    expect(recommendation.breakdown.optionA.costEur).toBe(20);
    expect(recommendation.breakdown.estimatedSavingsEur).toBe(25); // 45€ - 20€ = 25€ saved
  });

  it('honestly recommends plan downgrade when usage is <40% for 3 consecutive billing cycles', () => {
    // Current tier: Standard (79€/mo, 500 convs). Prev tier: Lite (29€/mo, 100 convs).
    // Usage across past 3 cycles: [20%, 25%, 30%] (< 40%).
    // Monthly savings = 79€ - 29€ = 50€/mo!
    const forecast = {
      dailyBurnRate: 2,
      daysRemainingInPeriod: 15,
      projectedTotalConversations: 60,
      projectedExhaustionDate: null,
      willExhaustBeforePeriodEnd: false
    };

    const recommendation = calculateHonestRecommendation({
      currentTier: 'standard',
      currentUsage: 40,
      includedConversations: 500,
      forecast,
      trailingCyclesUsagePercent: [20, 25, 30] // 3 consecutive cycles < 40%
    });

    expect(recommendation.type).toBe('downgrade_tier');
    expect(recommendation.breakdown.recommendedOption).toBe('Sales Ops Lite');
    expect(recommendation.breakdown.estimatedSavingsEur).toBe(50);
    expect(recommendation.headline).toContain('50€/mês');
  });
});
