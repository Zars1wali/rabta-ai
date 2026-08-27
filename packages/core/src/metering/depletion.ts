import type { Tier } from '@salesops/types';

export type DepletionState =
  | 'ok'
  | 'notice'
  | 'warning'
  | 'critical'
  | 'grace'
  | 'depleted';

export interface ModelRouteConfig {
  model: string;
  provider: 'google' | 'mistral-eu' | 'openai' | 'anthropic';
  maxHistory: number;
  maxOutputTokens: number;
  isEuResident: boolean;
  isDegraded: boolean;
}

export function computeDepletionState(
  conversationsUsed: number,
  includedConversations: number,
  overageAllowed = false
): DepletionState {
  if (includedConversations <= 0) return 'depleted';

  const percent = Math.round((conversationsUsed / includedConversations) * 10000) / 100;

  if (percent < 50) return 'ok';
  if (percent < 80) return 'notice';
  if (percent < 95) return 'warning';
  if (percent < 100) return 'critical';
  if (percent <= 110) return 'grace';

  // > 110%
  if (overageAllowed) {
    return 'grace';
  }
  return 'depleted';
}

export function resolveModelRoute(
  tier: Tier,
  depletionState: DepletionState
): ModelRouteConfig {
  const isDegraded =
    depletionState === 'critical' ||
    depletionState === 'grace' ||
    depletionState === 'depleted';

  // Europe tier: Non-negotiable EU Data Residency Rule
  if (tier === 'europe') {
    if (isDegraded) {
      return {
        model: 'mistral-small-latest',
        provider: 'mistral-eu',
        maxHistory: 8,
        maxOutputTokens: 300,
        isEuResident: true,
        isDegraded: true
      };
    }
    return {
      model: 'mistral-large-latest',
      provider: 'mistral-eu',
      maxHistory: 20,
      maxOutputTokens: 800,
      isEuResident: true,
      isDegraded: false
    };
  }

  // Premium tier
  if (tier === 'premium') {
    if (isDegraded) {
      return {
        model: 'gemini-2.0-flash',
        provider: 'google',
        maxHistory: 12,
        maxOutputTokens: 400,
        isEuResident: false,
        isDegraded: true
      };
    }
    return {
      model: 'gemini-2.5-pro',
      provider: 'google',
      maxHistory: 30,
      maxOutputTokens: 1000,
      isEuResident: false,
      isDegraded: false
    };
  }

  // Standard & Lite tiers
  if (isDegraded) {
    return {
      model: 'gemini-2.0-flash-lite',
      provider: 'google',
      maxHistory: 8,
      maxOutputTokens: 300,
      isEuResident: false,
      isDegraded: true
    };
  }

  return {
    model: 'gemini-2.0-flash',
    provider: 'google',
    maxHistory: 20,
    maxOutputTokens: 600,
    isEuResident: false,
    isDegraded: false
  };
}

export class SessionRouteStore {
  private routes = new Map<string, ModelRouteConfig>();

  getOrPinRoute(
    sessionId: string,
    tier: Tier,
    depletionState: DepletionState
  ): ModelRouteConfig {
    const existing = this.routes.get(sessionId);
    if (existing) {
      return existing;
    }

    const route = resolveModelRoute(tier, depletionState);
    this.routes.set(sessionId, route);
    return route;
  }

  clearSession(sessionId: string): void {
    this.routes.delete(sessionId);
  }
}
