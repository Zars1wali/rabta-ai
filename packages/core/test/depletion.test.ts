import { describe, it, expect } from 'vitest';
import {
  computeDepletionState,
  resolveModelRoute,
  SessionRouteStore
} from '../src/metering/index.js';

describe('Depletion State Machine & Route Degradation (WP-26)', () => {
  it('computes accurate depletion state across percentage thresholds', () => {
    const included = 100;

    expect(computeDepletionState(20, included)).toBe('ok'); // 20%
    expect(computeDepletionState(49, included)).toBe('ok'); // 49%
    expect(computeDepletionState(50, included)).toBe('notice'); // 50%
    expect(computeDepletionState(79, included)).toBe('notice'); // 79%
    expect(computeDepletionState(80, included)).toBe('warning'); // 80%
    expect(computeDepletionState(94, included)).toBe('warning'); // 94%
    expect(computeDepletionState(95, included)).toBe('critical'); // 95%
    expect(computeDepletionState(100, included)).toBe('grace'); // 100%
    expect(computeDepletionState(110, included)).toBe('grace'); // 110%
    expect(computeDepletionState(111, included, false)).toBe('depleted'); // 111% without overage
    expect(computeDepletionState(111, included, true)).toBe('grace'); // 111% with overage allowed
  });

  it('degrades Standard tier to Flash-Lite with 8 history turns when depleted/critical', () => {
    const normalRoute = resolveModelRoute('standard', 'ok');
    expect(normalRoute.model).toBe('gemini-2.0-flash');
    expect(normalRoute.maxHistory).toBe(20);
    expect(normalRoute.maxOutputTokens).toBe(600);
    expect(normalRoute.isDegraded).toBe(false);

    const degradedRoute = resolveModelRoute('standard', 'grace');
    expect(degradedRoute.model).toBe('gemini-2.0-flash-lite');
    expect(degradedRoute.maxHistory).toBe(8);
    expect(degradedRoute.maxOutputTokens).toBe(300);
    expect(degradedRoute.isDegraded).toBe(true);
  });

  it('strictly enforces Europe-tier EU data residency rule during degradation', () => {
    const normalEuropeRoute = resolveModelRoute('europe', 'ok');
    expect(normalEuropeRoute.model).toBe('mistral-large-latest');
    expect(normalEuropeRoute.provider).toBe('mistral-eu');
    expect(normalEuropeRoute.isEuResident).toBe(true);

    const degradedEuropeRoute = resolveModelRoute('europe', 'critical');
    // Europe tier MUST degrade to EU-resident Mistral Small, NEVER non-EU endpoints
    expect(degradedEuropeRoute.model).toBe('mistral-small-latest');
    expect(degradedEuropeRoute.provider).toBe('mistral-eu');
    expect(degradedEuropeRoute.isEuResident).toBe(true);
    expect(degradedEuropeRoute.maxHistory).toBe(8);
    expect(degradedEuropeRoute.maxOutputTokens).toBe(300);
    expect(degradedEuropeRoute.isDegraded).toBe(true);
  });

  it('pins session route at session start so route does not change mid-conversation', () => {
    const store = new SessionRouteStore();
    const sessionId = 'session-pinned-123';

    // 1. Initial turn when tenant is in 'ok' state
    const initialRoute = store.getOrPinRoute(sessionId, 'standard', 'ok');
    expect(initialRoute.model).toBe('gemini-2.0-flash');
    expect(initialRoute.isDegraded).toBe(false);

    // 2. Subsequent turn during same session after tenant state shifted to 'critical'
    const subsequentRoute = store.getOrPinRoute(sessionId, 'standard', 'critical');
    // Asserts session remains pinned to the initial route
    expect(subsequentRoute.model).toBe('gemini-2.0-flash');
    expect(subsequentRoute.isDegraded).toBe(false);

    // 3. New session created under 'critical' gets the degraded route
    const newSessionRoute = store.getOrPinRoute('new-session-456', 'standard', 'critical');
    expect(newSessionRoute.model).toBe('gemini-2.0-flash-lite');
    expect(newSessionRoute.isDegraded).toBe(true);
  });
});
