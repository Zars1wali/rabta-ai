import { describe, it, expect, vi } from 'vitest';
import { handleTopUpCheckoutRoute } from '../src/server/index.js';
import type { StripeBillingService } from '@salesops/core';
import { REWILT_TENANT_ID } from '@salesops/core';

describe('Billing Top-Up Actions Route (WP-28)', () => {
  const tenantId = REWILT_TENANT_ID;

  const mockBillingService = {
    createTopUpCheckoutSession: vi.fn().mockImplementation(async (options) => ({
      checkoutUrl: `https://checkout.stripe.com/pay/cs_test_topup?sku=topup_${options.blockCount * 100}`,
      sessionId: 'cs_test_topup',
      sku: `topup_${options.blockCount * 100}`,
      priceMinor: options.blockCount * 1500,
      currency: 'EUR',
      mode: 'payment'
    }))
  } as unknown as StripeBillingService;

  it('creates Stripe checkout session for 1x top-up block (+100 conversations for 15€)', async () => {
    const req = new Request('http://localhost/api/salesops/billing/topup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tenantId,
        blockCount: 1,
        email: 'loja@rewilt.com'
      })
    });

    const res = await handleTopUpCheckoutRoute(req, { billingService: mockBillingService });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.sku).toBe('topup_100');
    expect(data.priceMinor).toBe(1500); // 15€
    expect(data.checkoutUrl).toContain('topup_100');
  });

  it('creates Stripe checkout session for 2x top-up blocks (+200 conversations for 30€)', async () => {
    const req = new Request('http://localhost/api/salesops/billing/topup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tenantId,
        blockCount: 2,
        email: 'loja@rewilt.com'
      })
    });

    const res = await handleTopUpCheckoutRoute(req, { billingService: mockBillingService });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.sku).toBe('topup_200');
    expect(data.priceMinor).toBe(3000); // 30€
  });
});
