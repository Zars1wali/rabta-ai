import type { StripeBillingService } from '@salesops/core';
import type { SubscriptionRepository } from '@salesops/core';

export interface StripeWebhookRouteOptions {
  stripeService: StripeBillingService;
  subscriptionRepo: SubscriptionRepository;
  webhookSecret?: string;
}

export async function handleStripeWebhookRoute(
  req: Request,
  options: StripeWebhookRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const signature = req.headers.get('stripe-signature');
  const webhookSecret = options.webhookSecret || process.env.STRIPE_WEBHOOK_SECRET || 'whsec_test_secret';

  if (!signature) {
    return new Response(JSON.stringify({ error: 'Missing stripe-signature header' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const rawBody = await req.text();

  const isValid = options.stripeService.verifyWebhookSignature(
    rawBody,
    signature,
    webhookSecret
  );

  if (!isValid) {
    return new Response(JSON.stringify({ error: 'Invalid webhook signature' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const payload = JSON.parse(rawBody);
    const result = await options.stripeService.processWebhookEvent(
      payload,
      options.subscriptionRepo
    );

    return new Response(JSON.stringify({ received: true, result }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (err: unknown) {
    return new Response(
      JSON.stringify({ error: `Webhook processing error: ${(err as Error).message}` }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}
