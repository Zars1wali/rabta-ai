import { describe, it, expect } from 'vitest';
import {
  handlePrivacyPolicyRoute,
  handleTermsOfServiceRoute,
  handleDataProcessingAgreementRoute,
  handleUserDataDeletionCallback
} from '../src/server/legal.js';

describe('Legal & Compliance Routes (Swiss revDSG, EU AI Act, OR Art. 100)', () => {
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

  it('serves HTML terms of service with Swiss OR Art. 100 liability cap and indemnity clauses', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/terms');
    const res = handleTermsOfServiceRoute(req);
    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toContain('text/html');
    const text = await res.text();
    expect(text).toContain('Terms of Service');
    expect(text).toContain('Nuno Miguel Pires Ribeiro');
    expect(text).toContain('OR Art. 100');
    expect(text).toContain('CHF 500.00');
    expect(text).toContain('Merchant Indemnification');
    expect(text).toContain('Canton of Zurich');
    expect(text).toContain('Invitatio ad offerendum');
  });

  it('serves JSON terms of service metadata with liability shield parameters', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/terms', {
      headers: { Accept: 'application/json' }
    });
    const res = handleTermsOfServiceRoute(req);
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.governingLaw).toContain('Switzerland');
    expect(json.liabilityCap).toContain('OR Art. 100');
    expect(json.merchantIndemnity).toBeDefined();
  });

  it('serves HTML Data Processing Agreement (DPA) in compliance with revDSG and GDPR', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/dpa');
    const res = handleDataProcessingAgreementRoute(req);
    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toContain('text/html');
    const text = await res.text();
    expect(text).toContain('Data Processing Agreement');
    expect(text).toContain('Data Controller');
    expect(text).toContain('Data Processor');
    expect(text).toContain('Row-Level Security');
    expect(text).toContain('Canton of Zurich');
  });

  it('serves JSON DPA metadata specifying controller/processor allocation and TOMs', async () => {
    const req = new Request('https://nuncio.zeropointintel.com/dpa', {
      headers: { Accept: 'application/json' }
    });
    const res = handleDataProcessingAgreementRoute(req);
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.legalFramework).toContain('revDSG');
    expect(json.roleAllocation.merchant).toContain('Data Controller');
    expect(json.roleAllocation.vendor).toContain('Data Processor');
    expect(json.technicalOrganizationalMeasures.length).toBeGreaterThanOrEqual(3);
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
