import { describe, it, expect, vi } from 'vitest';
import { handleLeadRoute } from '../src/server/index.js';
import type {
  SessionRepository,
  LeadRepository,
  TenantRepository,
  NotificationDispatcher
} from '@salesops/core';
import { REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '@salesops/core';

describe('Lead Capture & Consent API Route (WP-13)', () => {
  const tenantId = REWILT_TENANT_ID;
  const sessionId = '00000000-0000-4000-8000-000000000099';

  const mockTenantRepo = {
    getById: vi.fn().mockResolvedValue({
      id: tenantId,
      displayName: 'Rewilt Sales Ops',
      config: REWILT_TENANT_CONFIG
    })
  } as unknown as TenantRepository;

  const mockSessionRepo = {
    getSession: vi.fn().mockResolvedValue({
      id: sessionId,
      tenantId,
      tokensUsed: 100,
      consentAt: null
    }),
    updateTurn: vi.fn().mockResolvedValue({ id: sessionId })
  } as unknown as SessionRepository;

  const mockLeadRepo = {
    createLead: vi.fn().mockImplementation(async (data) => ({
      id: 'lead-created-123',
      ...data,
      createdAt: new Date().toISOString()
    }))
  } as unknown as LeadRepository;

  const mockDispatcher: NotificationDispatcher = {
    dispatch: vi.fn().mockResolvedValue({ sent: true, channel: 'webhook', target: 'http://test' })
  };

  it('rejects lead submission with 400 when GDPR consent is false', async () => {
    const req = new Request('http://localhost/api/salesops/lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tenantId,
        sessionId,
        consent: false, // INVALID / REFUSED
        name: 'Maria Santos',
        email: 'maria@loja.pt'
      })
    });

    const res = await handleLeadRoute(req, {
      sessionRepo: mockSessionRepo,
      leadRepo: mockLeadRepo,
      tenantRepo: mockTenantRepo,
      notificationDispatcher: mockDispatcher
    });

    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.error).toContain('Validation failed');
    expect(mockLeadRepo.createLead).not.toHaveBeenCalled();
  });

  it('persists lead, records consent, and triggers notification when consent is true', async () => {
    const req = new Request('http://localhost/api/salesops/lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tenantId,
        sessionId,
        consent: true, // EXPLICIT CONSENT
        name: 'Maria Santos',
        email: 'maria@loja.pt',
        phone: '912345678',
        companyUrl: 'https://marialoja.pt',
        notes: 'Pretende plano Standard'
      })
    });

    const res = await handleLeadRoute(req, {
      sessionRepo: mockSessionRepo,
      leadRepo: mockLeadRepo,
      tenantRepo: mockTenantRepo,
      notificationDispatcher: mockDispatcher
    });

    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.ok).toBe(true);
    expect(data.leadId).toBe('lead-created-123');
    expect(data.status).toBe('recorded');

    expect(mockLeadRepo.createLead).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantId,
        sessionId,
        name: 'Maria Santos',
        email: 'maria@loja.pt'
      })
    );

    expect(mockDispatcher.dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'lead_captured',
        tenantId,
        sessionId
      })
    );
  });
});
