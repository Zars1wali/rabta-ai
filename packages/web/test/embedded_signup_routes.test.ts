import { describe, it, expect, vi } from 'vitest';
import {
  handleEmbeddedSignupConfigRoute,
  handleEmbeddedSignupCallbackRoute
} from '../src/server/embedded_signup.js';
import { MetaEmbeddedSignupService } from '@salesops/core';

describe('Meta Embedded Signup Server Routes', () => {
  it('GET /api/waba/embedded-signup/config returns App ID and Meta configuration', async () => {
    const service = new MetaEmbeddedSignupService({
      appId: '1584644373301704',
      appSecret: 'test_secret'
    });

    const req = new Request('http://localhost:3000/api/waba/embedded-signup/config?tenantId=test_tenant', {
      method: 'GET'
    });

    const res = await handleEmbeddedSignupConfigRoute(req, { service });
    expect(res.status).toBe(200);

    const json = await res.json();
    expect(json.appId).toBe('1584644373301704');
    expect(json.state).toBe('test_tenant');
    expect(json.version).toBe('v21.0');
  });

  it('POST /api/waba/embedded-signup/callback exchanges OAuth code and provisions WABA channel', async () => {
    const mockFetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/oauth/access_token')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ access_token: 'EAATestToken123' })
        });
      }
      if (url.includes('/debug_token')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              data: {
                granular_scopes: [{ target_ids: ['1406719968069623'] }]
              }
            })
        });
      }
      if (url.includes('/phone_numbers')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              data: [{ id: '104829384729182', display_phone_number: '+41 79 123 45 67' }]
            })
        });
      }
      if (url.includes('/subscribed_apps')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true })
        });
      }
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
    });

    const service = new MetaEmbeddedSignupService({
      appId: '1584644373301704',
      appSecret: 'test_secret',
      fetchFn: mockFetch as any
    });

    const mockChannelRepo = {
      createChannel: vi.fn().mockResolvedValue({ id: 'chan_001' })
    };

    const req = new Request('http://localhost:3000/api/waba/embedded-signup/callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: 'AQD_test_oauth_code_123',
        tenantId: '11111111-1111-4111-8111-111111111111'
      })
    });

    const res = await handleEmbeddedSignupCallbackRoute(req, {
      service,
      channelRepo: mockChannelRepo as any
    });

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.ok).toBe(true);
    expect(json.accessToken).toBe('EAATestToken123');
    expect(json.wabaId).toBe('1406719968069623');
    expect(json.phoneNumberId).toBe('104829384729182');
    expect(json.displayPhoneNumber).toBe('+41 79 123 45 67');

    expect(mockChannelRepo.createChannel).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantId: '11111111-1111-4111-8111-111111111111',
        type: 'whatsapp',
        wabaId: '1406719968069623',
        phoneNumberId: '104829384729182',
        status: 'active'
      })
    );
  });
});
