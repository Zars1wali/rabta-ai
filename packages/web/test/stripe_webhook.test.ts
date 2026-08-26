import { describe, it, expect, vi } from 'vitest';
import crypto from 'node:crypto';
import { handleStripeWebhookRoute, handleCustomerPortalRoute } from '../src/server/index.js';
import { StripeBillingService, type SubscriptionRepository } from '@salesops/core';
import { REWILT_TENANT_ID } from '@salesops/core';

describe('Stripe Webhook & Portal API Routes (WP-12)', () => {
  const stripeService = new StripeBillingService();
  const webhookSecret = 'whsec_test_secret_abc123';

  const createSignedRequest = (payload: Record<string, unknown>, secret = webhookSecret) => {
    const rawBody = JSON.stringify(payload);
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const signedPayload = `${timestamp}.${rawBody}`;
    const hmac = crypto.createHmac('sha256', secret).update(signedPayload).digest('hex');
    const signatureHeader = `t=${timestamp},v1=${hmac}`;

    return new Request('http://localhost/api/salesops/webhooks/stripe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'stripe-signature': signatureHeader
      },
      body: rawBody
    });
  };

  describe('handleStripeWebhookRoute', () => {
    it('returns 400 Bad Request if stripe-signature header is missing', async () => {
      const req = new Request('http://localhost/api/salesops/webhooks/stripe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'checkout.session.completed' })
      });

      const res = await handleStripeWebhookRoute(req, {
        stripeService,
        subscriptionRepo: {} as SubscriptionRepository,
        webhookSecret
      });

      expect(res.status).toBe(400);
      const data = await res.json();
      expect(data.error).toContain('Missing stripe-signature header');
    });

    it('returns 400 Bad Request if signature is invalid or forged', async () => {
      // Signed with a different secret
      const req = createSignedRequest({ type: 'checkout.session.completed' }, 'wrong_secret');

      const res = await handleStripeWebhookRoute(req, {
        stripeService,
        subscriptionRepo: {} as SubscriptionRepository,
        webhookSecret
      });

      expect(res.status).toBe(400);
      const data = await res.json();
      expect(data.error).toContain('Invalid webhook signature');
    });

    it('returns 200 OK and processes checkout.session.completed when signature is valid', async () => {
      const mockSubRepo = {
        upsertSubscription: vi.fn().mockResolvedValue({ id: 'sub-active-123' })
      } as unknown as SubscriptionRepository;

      const payload = {
        id: 'evt_stripe_1',
        type: 'checkout.session.completed',
        data: {
          object: {
            id: 'cs_sub_test123',
            customer: 'cus_client_1',
            subscription: 'sub_live_1',
            mode: 'subscription',
            metadata: {
              tenant_id: REWILT_TENANT_ID,
              session_id: 'session-123'
            }
          }
        }
      };

      const req = createSignedRequest(payload, webhookSecret);
      const res = await handleStripeWebhookRoute(req, {
        stripeService,
        subscriptionRepo: mockSubRepo,
        webhookSecret
      });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data.received).toBe(true);
      expect(data.result.action).toBe('checkout_completed');
      expect(data.result.subscriptionId).toBe('sub-active-123');
    });
  });

  describe('handleCustomerPortalRoute', () => {
    it('generates billing portal session URL for active subscription', async () => {
      const mockSubRepo = {
        getByTenantId: vi.fn().mockResolvedValue([
          {
            id: 'sub-1',
            tenantId: REWILT_TENANT_ID,
            stripeCustomerId: 'cus_client_1',
            status: 'active'
          }
        ])
      } as unknown as SubscriptionRepository;

      const req = new Request('http://localhost/api/salesops/billing/portal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenantId: REWILT_TENANT_ID, returnUrl: 'https://rewilt.com/dash' })
      });

      const res = await handleCustomerPortalRoute(req, {
        stripeService,
        subscriptionRepo: mockSubRepo
      });

      expect(res.status).toBe(200);
      const data = await res.json();
      expect(data.portalUrl).toContain('billing.stripe.com');
      expect(data.portalUrl).toContain('cus_client_1');
    });
  });
});
