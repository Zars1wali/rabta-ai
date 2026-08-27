import { describe, it, expect, vi } from 'vitest';
import { WabaOnboardingService } from '../src/channels/index.js';

describe('WABA Onboarding & Number Provisioning (WP-20)', () => {
  it('registers phone number with Meta Graph API using 6-digit pin', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true })
    });

    const wabaService = new WabaOnboardingService({
      accessToken: 'test_meta_token',
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await wabaService.registerPhoneNumber({
      phoneNumberId: 'phone_123456',
      pin: '123456'
    });

    expect(res.ok).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('phone_123456/register'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test_meta_token' }),
        body: JSON.stringify({ messaging_product: 'whatsapp', pin: '123456' })
      })
    );
  });

  it('retrieves phone number status and quality rating', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'phone_123456',
        verified_name: 'Rewilt Portugal',
        display_phone_number: '+351 912 345 678',
        quality_rating: 'GREEN',
        status: 'CONNECTED',
        code_verification_status: 'VERIFIED'
      })
    });

    const wabaService = new WabaOnboardingService({
      accessToken: 'test_meta_token',
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await wabaService.getPhoneNumberStatus({
      phoneNumberId: 'phone_123456'
    });

    expect(res.ok).toBe(true);
    expect(res.status?.verifiedName).toBe('Rewilt Portugal');
    expect(res.status?.displayPhoneNumber).toBe('+351 912 345 678');
    expect(res.status?.qualityRating).toBe('GREEN');
    expect(res.status?.status).toBe('CONNECTED');
  });
});
