import { describe, it, expect, vi } from 'vitest';
import {
  handleWabaRegisterRoute,
  handleWabaStatusRoute
} from '../src/server/index.js';
import type { WabaOnboardingService } from '@salesops/core';

describe('WABA Onboarding Web Routes (WP-20)', () => {
  const mockWabaService = {
    registerPhoneNumber: vi.fn().mockResolvedValue({ ok: true }),
    getPhoneNumberStatus: vi.fn().mockResolvedValue({
      ok: true,
      status: {
        id: 'phone_123456',
        verifiedName: 'Rewilt Portugal',
        displayPhoneNumber: '+351 912 345 678',
        qualityRating: 'GREEN',
        status: 'CONNECTED',
        codeVerificationStatus: 'VERIFIED'
      }
    })
  } as unknown as WabaOnboardingService;

  it('registers phone number via POST /api/salesops/channels/whatsapp/register', async () => {
    const req = new Request('http://localhost/api/salesops/channels/whatsapp/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phoneNumberId: 'phone_123456',
        pin: '123456'
      })
    });

    const res = await handleWabaRegisterRoute(req, { wabaService: mockWabaService });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.ok).toBe(true);
    expect(mockWabaService.registerPhoneNumber).toHaveBeenCalledWith(
      expect.objectContaining({ phoneNumberId: 'phone_123456', pin: '123456' })
    );
  });

  it('retrieves phone number status via GET /api/salesops/channels/whatsapp/status', async () => {
    const req = new Request(
      'http://localhost/api/salesops/channels/whatsapp/status?phoneNumberId=phone_123456',
      {
        headers: { Authorization: 'Bearer token_abc' }
      }
    );

    const res = await handleWabaStatusRoute(req, { wabaService: mockWabaService });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.ok).toBe(true);
    expect(data.status.verifiedName).toBe('Rewilt Portugal');
    expect(data.status.qualityRating).toBe('GREEN');
  });
});
