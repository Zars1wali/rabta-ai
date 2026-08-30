import { describe, it, expect } from 'vitest';
import {
  ServiceWindowEngine,
  ServiceWindowExpiredError,
  defaultServiceWindowEngine
} from '../src/channels/service_window.js';

describe('ServiceWindowEngine', () => {
  const engine = defaultServiceWindowEngine;

  it('calculates open service window within 24 hours of customer inbound', () => {
    const now = new Date('2026-08-30T12:00:00Z');
    const inboundAt = new Date('2026-08-30T10:00:00Z'); // 2 hours ago

    const status = engine.calculateServiceWindow(inboundAt, now);

    expect(status.isOpen).toBe(true);
    expect(status.remainingMs).toBe(22 * 60 * 60 * 1000);
    expect(status.isExpiringSoon).toBe(false);
    expect(status.expiresAt.toISOString()).toBe('2026-08-31T10:00:00.000Z');
  });

  it('flags expiring soon if less than 2 hours remain in customer window', () => {
    const now = new Date('2026-08-30T12:00:00Z');
    const inboundAt = new Date('2026-08-29T13:00:00Z'); // 23 hours ago (1h remaining)

    const status = engine.calculateServiceWindow(inboundAt, now);

    expect(status.isOpen).toBe(true);
    expect(status.isExpiringSoon).toBe(true);
    expect(status.remainingMs).toBe(1 * 60 * 60 * 1000);
  });

  it('detects expired service window (>24 hours) and closes window', () => {
    const now = new Date('2026-08-30T15:00:00Z');
    const inboundAt = new Date('2026-08-29T10:00:00Z'); // 29 hours ago

    const status = engine.calculateServiceWindow(inboundAt, now);

    expect(status.isOpen).toBe(false);
    expect(status.remainingMs).toBe(0);
    expect(status.isExpiringSoon).toBe(false);
  });

  it('assertOutboundAllowed throws ServiceWindowExpiredError when window is closed', () => {
    const now = new Date('2026-08-30T15:00:00Z');
    const inboundAt = new Date('2026-08-29T10:00:00Z'); // expired

    expect(() => engine.assertOutboundAllowed(inboundAt, now)).toThrowError(
      ServiceWindowExpiredError
    );
  });

  it('assertOutboundAllowed passes cleanly when window is open', () => {
    const now = new Date('2026-08-30T12:00:00Z');
    const inboundAt = new Date('2026-08-30T11:00:00Z');

    expect(() => engine.assertOutboundAllowed(inboundAt, now)).not.toThrow();
  });

  it('estimates billing category costs accurately for Swiss and EU markets', () => {
    const chEstimate = engine.estimateMessageCost('service', 'CH');
    expect(chEstimate.category).toBe('service');
    expect(chEstimate.currency).toBe('CHF');
    expect(chEstimate.estimatedCostMinor).toBe(4);
    expect(chEstimate.isFreeTierEligible).toBe(true);

    const euMarketing = engine.estimateMessageCost('marketing', 'EU');
    expect(euMarketing.currency).toBe('EUR');
    expect(euMarketing.estimatedCostMinor).toBe(6);
    expect(euMarketing.isFreeTierEligible).toBe(false);
  });
});
