import { describe, it, expect, vi } from 'vitest';
import { OutboundNotificationDispatcher } from '../src/notifications/index.js';
import { REWILT_TENANT_ID } from '../src/db/seed.js';
import type { Lead } from '@salesops/types';

describe('Outbound Notification Dispatcher (WP-13)', () => {
  const tenantId = REWILT_TENANT_ID;
  const sessionId = '00000000-0000-4000-8000-000000000099';

  const mockLead: Lead = {
    id: 'lead-test-1',
    tenantId,
    sessionId,
    name: 'Carlos Oliveira',
    email: 'carlos@loja.pt',
    phone: '912345678',
    companyUrl: 'https://carlosloja.pt',
    notes: 'Interesse no plano Standard',
    consentAt: new Date().toISOString(),
    createdAt: new Date().toISOString()
  };

  it('dispatches webhook POST with valid payload when webhookUrl is configured', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200
    });

    const dispatcher = new OutboundNotificationDispatcher({
      webhookUrl: 'https://hooks.slack.com/services/T00/B00/X00',
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await dispatcher.dispatch({
      type: 'lead_captured',
      tenantId,
      sessionId,
      lead: mockLead
    });

    expect(res.sent).toBe(true);
    expect(res.channel).toBe('webhook');
    expect(mockFetch).toHaveBeenCalledWith(
      'https://hooks.slack.com/services/T00/B00/X00',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' })
      })
    );
  });

  it('dispatches email escalation notification for handoff_requested event', async () => {
    const dispatcher = new OutboundNotificationDispatcher({
      defaultEmailTarget: 'suporte@rewilt.com'
    });

    const res = await dispatcher.dispatch({
      type: 'handoff_requested',
      tenantId,
      sessionId,
      reason: 'Cliente solicita integração ERP personalizada',
      target: { type: 'email', to: 'comercial@rewilt.com' }
    });

    expect(res.sent).toBe(true);
    expect(res.channel).toBe('email');
    expect(res.target).toBe('comercial@rewilt.com');
  });

  it('handles webhook network failure gracefully without crashing', async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error('Network connection timeout'));

    const dispatcher = new OutboundNotificationDispatcher({
      webhookUrl: 'https://unreachable-webhook.com/hook',
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await dispatcher.dispatch({
      type: 'lead_captured',
      tenantId,
      sessionId,
      lead: mockLead
    });

    expect(res.sent).toBe(false);
    expect(res.error).toContain('Network connection timeout');
  });
});
