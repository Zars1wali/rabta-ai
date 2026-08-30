import { describe, it, expect } from 'vitest';
import {
  handlePrivacyPolicyRoute,
  handleTermsOfServiceRoute,
  handleUserDataDeletionCallback
} from '../src/server/legal.js';

describe('Legal & Compliance Routes', () => {
  it('serves HTML privacy policy by default', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/privacy');
    const res = handlePrivacyPolicyRoute(req);
    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toContain('text/html');
    const text = await res.text();
    expect(text).toContain('Privacy Policy');
    expect(text).toContain('Nuno Miguel Pires Ribeiro');
    expect(text).toContain('user-data-deletion');
  });

  it('serves JSON privacy policy metadata when requested', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/privacy', {
      headers: { Accept: 'application/json' }
    });
    const res = handlePrivacyPolicyRoute(req);
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.title).toBe('Privacy Policy');
    expect(json.controller).toBe('Nuno Miguel Pires Ribeiro');
    expect(json.subProcessors).toHaveLength(5);
  });

  it('serves HTML terms of service by default', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/terms');
    const res = handleTermsOfServiceRoute(req);
    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toContain('text/html');
    const text = await res.text();
    expect(text).toContain('Terms of Service');
    expect(text).toContain('Nuno Miguel Pires Ribeiro');
  });

  it('handles user data deletion callback POST request', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/api/user-data-deletion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'wa_12345' })
    });
    const res = await handleUserDataDeletionCallback(req);
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.status).toBe('queued');
    expect(json.confirmation_code).toMatch(/^del_\d+_/);
  });
});
