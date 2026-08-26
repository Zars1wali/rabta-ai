export type StripeProductPlan =
  | 'salesops_lite'
  | 'salesops_standard'
  | 'salesops_europe'
  | 'salesops_premium'
  | 'salesops_preview';

export const STRIPE_PRICE_LOOKUP_KEYS: Record<StripeProductPlan, string> = {
  salesops_lite: 'salesops_lite_monthly_eur',
  salesops_standard: 'salesops_standard_monthly_eur',
  salesops_europe: 'salesops_europe_monthly_eur',
  salesops_premium: 'salesops_premium_monthly_eur',
  salesops_preview: 'salesops_preview_eur'
};

export const STRIPE_PLAN_AMOUNTS_MINOR: Record<StripeProductPlan, number> = {
  salesops_lite: 2900,
  salesops_standard: 7900,
  salesops_europe: 9900,
  salesops_premium: 19900,
  salesops_preview: 5000
};

export interface CreateCheckoutSessionOptions {
  tenantId: string;
  sessionId: string;
  sku: string;
  email?: string;
  locale?: string;
  mode?: 'subscription' | 'payment';
  successUrl?: string;
  cancelUrl?: string;
  metadata?: Record<string, string>;
}

export interface StripeCheckoutResult {
  checkoutUrl: string;
  sessionId: string;
  sku: string;
  priceMinor: number;
  currency: string;
  mode: 'subscription' | 'payment';
}

export interface StripeCustomerPortalOptions {
  customerId: string;
  returnUrl: string;
}

export interface StripeWebhookPayload {
  id: string;
  type: string;
  data: {
    object: Record<string, unknown>;
  };
}
