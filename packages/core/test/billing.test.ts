import { describe, it, expect, vi } from 'vitest';
import crypto from 'node:crypto';
import {
  StripeBillingService,
  STRIPE_PRICE_LOOKUP_KEYS,
  STRIPE_PLAN_AMOUNTS_MINOR
} from '../src/billing/index.js';
import type { SubscriptionRepository } from '../src/db/repositories.js';
import { REWILT_TENANT_ID } from '../src/db/seed.js';

describe('Stripe Billing & Checkout Services (WP-12)', () => {
  const service = new StripeBillingService();
  const tenantId = REWILT_TENANT_ID;
  const sessionId = '00000000-0000-4000-8000-000000000099';
  const webhookSecret = 'whsec_test_secret_12345';

  describe('Lookup Keys and Minor Units Configuration', () => {
    it('maps all 5 plans to correct lookup keys and price amounts', () => {
      expect(STRIPE_PRICE_LOOKUP_KEYS.salesops_lite).toBe('salesops_lite_monthly_eur');
      expect(STRIPE_PRICE_LOOKUP_KEYS.salesops_standard).toBe('salesops_standard_monthly_eur');
      expect(STRIPE_PRICE_LOOKUP_KEYS.salesops_europe).toBe('salesops_europe_monthly_eur');
      expect(STRIPE_PRICE_LOOKUP_KEYS.salesops_premium).toBe('salesops_premium_monthly_eur');
      expect(STRIPE_PRICE_LOOKUP_KEYS.salesops_preview).toBe('salesops_preview_eur');

      expect(STRIPE_PLAN_AMOUNTS_MINOR.salesops_lite).toBe(2900); // 29 EUR
      expect(STRIPE_PLAN_AMOUNTS_MINOR.salesops_standard).toBe(7900); // 79 EUR
      expect(STRIPE_PLAN_AMOUNTS_MINOR.salesops_europe).toBe(9900); // 99 EUR
      expect(STRIPE_PLAN_AMOUNTS_MINOR.salesops_premium).toBe(19900); // 199 EUR
      expect(STRIPE_PLAN_AMOUNTS_MINOR.salesops_preview).toBe(5000); // 50 EUR
    });
  });

  describe('createCheckoutSession', () => {
    it('creates a subscription checkout session for Standard plan', async () => {
      const session = await service.createCheckoutSession({
        tenantId,
        sessionId,
        sku: 'salesops_standard'
      });

      expect(session.checkoutUrl).toContain('checkout.stripe.com');
      expect(session.checkoutUrl).toContain('salesops_standard_monthly_eur');
      expect(session.priceMinor).toBe(7900);
      expect(session.mode).toBe('subscription');
    });

    it('creates a one-time payment checkout session for 50 EUR custom preview', async () => {
      const session = await service.createCheckoutSession({
        tenantId,
        sessionId,
        sku: 'salesops_preview'
      });

      expect(session.checkoutUrl).toContain('checkout.stripe.com');
      expect(session.priceMinor).toBe(5000);
      expect(session.mode).toBe('payment');
    });
  });

  describe('createCustomerPortalSession', () => {
    it('creates a customer portal session URL for an active subscriber', async () => {
      const portal = await service.createCustomerPortalSession({
        customerId: 'cus_test_123',
        returnUrl: 'https://rewilt.com/dashboard'
      });

      expect(portal.portalUrl).toContain('billing.stripe.com/p/session');
      expect(portal.portalUrl).toContain('cus_test_123');
    });
  });

  describe('verifyWebhookSignature', () => {
    it('validates a correctly computed Stripe signature header', () => {
      const payload = JSON.stringify({ id: 'evt_123', type: 'checkout.session.completed' });
      const timestamp = Math.floor(Date.now() / 1000).toString();
      const signedPayload = `${timestamp}.${payload}`;
      const hmac = crypto.createHmac('sha256', webhookSecret).update(signedPayload).digest('hex');
      const signatureHeader = `t=${timestamp},v1=${hmac}`;

      const isValid = service.verifyWebhookSignature(payload, signatureHeader, webhookSecret);
      expect(isValid).toBe(true);
    });

    it('rejects an invalid signature header', () => {
      const payload = JSON.stringify({ id: 'evt_123' });
      const signatureHeader = `t=123456,v1=tampered_signature`;

      const isValid = service.verifyWebhookSignature(payload, signatureHeader, webhookSecret);
      expect(isValid).toBe(false);
    });
  });

  describe('processWebhookEvent', () => {
    it('provisions subscription on checkout.session.completed', async () => {
      const mockSubRepo = {
        upsertSubscription: vi.fn().mockResolvedValue({ id: 'sub-row-1' })
      } as unknown as SubscriptionRepository;

      const event = {
        id: 'evt_1',
        type: 'checkout.session.completed',
        data: {
          object: {
            id: 'cs_123',
            customer: 'cus_999',
            subscription: 'sub_stripe_888',
            mode: 'subscription',
            metadata: {
              tenant_id: tenantId,
              session_id: sessionId
            }
          }
        }
      };

      const res = await service.processWebhookEvent(event, mockSubRepo);

      expect(res.processed).toBe(true);
      expect(res.action).toBe('checkout_completed');
      expect(res.subscriptionId).toBe('sub-row-1');
      expect(mockSubRepo.upsertSubscription).toHaveBeenCalledWith(
        expect.objectContaining({
          tenantId,
          sessionId,
          stripeCustomerId: 'cus_999',
          stripeSubscriptionId: 'sub_stripe_888',
          kind: 'subscription',
          status: 'active'
        })
      );
    });

    it('updates subscription status on customer.subscription.deleted', async () => {
      const mockSubRepo = {
        upsertSubscription: vi.fn().mockResolvedValue({ id: 'sub-row-1' })
      } as unknown as SubscriptionRepository;

      const event = {
        id: 'evt_2',
        type: 'customer.subscription.deleted',
        data: {
          object: {
            id: 'sub_stripe_888',
            customer: 'cus_999',
            status: 'canceled',
            metadata: {
              tenant_id: tenantId
            }
          }
        }
      };

      const res = await service.processWebhookEvent(event, mockSubRepo);

      expect(res.processed).toBe(true);
      expect(res.action).toBe('subscription_deleted');
      expect(mockSubRepo.upsertSubscription).toHaveBeenCalledWith(
        expect.objectContaining({
          stripeSubscriptionId: 'sub_stripe_888',
          status: 'canceled'
        })
      );
    });
  });
});
