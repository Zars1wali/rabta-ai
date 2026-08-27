import crypto from 'node:crypto';
import type {
  CreateCheckoutSessionOptions,
  StripeCheckoutResult,
  StripeCustomerPortalOptions,
  StripeProductPlan,
  StripeWebhookPayload
} from './types.js';
import { STRIPE_PLAN_AMOUNTS_MINOR, STRIPE_PRICE_LOOKUP_KEYS } from './types.js';
import type { SubscriptionRepository } from '../db/repositories.js';

export interface StripeBillingServiceOptions {
  stripeSecretKey?: string;
  defaultSuccessUrl?: string;
  defaultCancelUrl?: string;
}

interface StripeEventObject {
  id?: string;
  customer?: string;
  subscription?: string | null;
  mode?: string;
  status?: string;
  client_reference_id?: string;
  metadata?: Record<string, string>;
}

export class StripeBillingService {
  private secretKey?: string;
  private defaultSuccessUrl: string;
  private defaultCancelUrl: string;

  constructor(options?: StripeBillingServiceOptions) {
    this.secretKey = options?.stripeSecretKey || process.env.STRIPE_SECRET_KEY;
    this.defaultSuccessUrl = options?.defaultSuccessUrl || 'https://rewilt.com/checkout/success';
    this.defaultCancelUrl = options?.defaultCancelUrl || 'https://rewilt.com/checkout/cancel';
  }

  async createCheckoutSession(
    options: CreateCheckoutSessionOptions
  ): Promise<StripeCheckoutResult> {
    const planKey = options.sku as StripeProductPlan;
    const priceMinor = STRIPE_PLAN_AMOUNTS_MINOR[planKey] ?? 7900;
    const mode = options.mode || (options.sku === 'salesops_preview' ? 'payment' : 'subscription');
    const lookupKey = STRIPE_PRICE_LOOKUP_KEYS[planKey] || 'salesops_standard_monthly_eur';

    const checkoutSessionId = `cs_${mode === 'subscription' ? 'sub' : 'pay'}_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
    const checkoutUrl = `https://checkout.stripe.com/pay/${checkoutSessionId}?lookup_key=${encodeURIComponent(lookupKey)}&tenant_id=${encodeURIComponent(options.tenantId)}`;

    return {
      checkoutUrl,
      sessionId: checkoutSessionId,
      sku: options.sku,
      priceMinor,
      currency: 'EUR',
      mode
    };
  }

  async createTopUpCheckoutSession(options: {
    tenantId: string;
    blockCount: number;
    email?: string;
    successUrl?: string;
    cancelUrl?: string;
  }): Promise<StripeCheckoutResult> {
    const blocks = Math.max(1, options.blockCount || 1);
    const priceMinor = blocks * 1500; // 15€ = 1500 cents per 100 conversations
    const sessionId = `cs_topup_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
    const checkoutUrl = `https://checkout.stripe.com/pay/${sessionId}?sku=topup_${blocks * 100}&tenant_id=${encodeURIComponent(options.tenantId)}`;

    return {
      checkoutUrl,
      sessionId,
      sku: `topup_${blocks * 100}`,
      priceMinor,
      currency: 'EUR',
      mode: 'payment'
    };
  }

  async createCustomerPortalSession(
    options: StripeCustomerPortalOptions
  ): Promise<{ portalUrl: string }> {
    const portalSessionId = `bps_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
    const portalUrl = `https://billing.stripe.com/p/session/${portalSessionId}?customer=${encodeURIComponent(options.customerId)}`;
    return { portalUrl };
  }

  verifyWebhookSignature(
    rawBody: string,
    signatureHeader: string,
    webhookSecret: string
  ): boolean {
    if (!signatureHeader || !webhookSecret) return false;

    // Header format: t=1612345678,v1=5257a869e7ecebeda32affa62cd...
    const parts = signatureHeader.split(',');
    let timestamp = '';
    const signatures: string[] = [];

    for (const part of parts) {
      const [key, value] = part.trim().split('=');
      if (key === 't' && value) timestamp = value;
      if (key === 'v1' && value) signatures.push(value);
    }

    if (!timestamp || signatures.length === 0) return false;

    const payload = `${timestamp}.${rawBody}`;
    const expectedSignature = crypto
      .createHmac('sha256', webhookSecret)
      .update(payload, 'utf8')
      .digest('hex');

    return signatures.some((sig) => {
      if (sig.length !== expectedSignature.length) return false;
      return crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expectedSignature));
    });
  }

  async processWebhookEvent(
    event: StripeWebhookPayload,
    subscriptionRepo: SubscriptionRepository
  ): Promise<{ processed: boolean; action: string; subscriptionId?: string }> {
    const obj = event.data.object as StripeEventObject;

    if (event.type === 'checkout.session.completed') {
      const tenantId = obj.metadata?.tenant_id || obj.client_reference_id;
      const sessionId = obj.metadata?.session_id;
      const stripeCustomerId = obj.customer || `cus_${crypto.randomUUID().slice(0, 8)}`;
      const stripeSubscriptionId = obj.subscription || null;
      const stripeCheckoutId = obj.id;
      const mode = obj.mode === 'payment' ? 'preview' : 'subscription';

      if (!tenantId) {
        return { processed: false, action: 'ignored_missing_tenant' };
      }

      const sub = await subscriptionRepo.upsertSubscription({
        tenantId,
        sessionId,
        stripeCustomerId,
        stripeSubscriptionId,
        stripeCheckoutId,
        kind: mode,
        status: 'active'
      });

      return {
        processed: true,
        action: 'checkout_completed',
        subscriptionId: sub.id
      };
    }

    if (
      event.type === 'customer.subscription.created' ||
      event.type === 'customer.subscription.updated' ||
      event.type === 'customer.subscription.deleted'
    ) {
      const tenantId = obj.metadata?.tenant_id;
      const stripeSubscriptionId = obj.id;
      const stripeCustomerId = obj.customer || `cus_${crypto.randomUUID().slice(0, 8)}`;
      const status = obj.status || (event.type === 'customer.subscription.deleted' ? 'canceled' : 'active');

      if (!tenantId && !stripeSubscriptionId) {
        return { processed: false, action: 'ignored_missing_id' };
      }

      const sub = await subscriptionRepo.upsertSubscription({
        tenantId: tenantId || '00000000-0000-0000-0000-000000000000',
        stripeCustomerId,
        stripeSubscriptionId,
        kind: 'subscription',
        status
      });

      return {
        processed: true,
        action: `subscription_${event.type.split('.').pop()}`,
        subscriptionId: sub.id
      };
    }

    return { processed: false, action: 'unhandled_event_type' };
  }
}

export const defaultStripeService = new StripeBillingService();
