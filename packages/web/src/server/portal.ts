import type { StripeBillingService } from '@salesops/core';
import type { SubscriptionRepository } from '@salesops/core';

export interface CustomerPortalRouteOptions {
  stripeService: StripeBillingService;
  subscriptionRepo: SubscriptionRepository;
}

export async function handleCustomerPortalRoute(
  req: Request,
  options: CustomerPortalRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await req.json();
    const { tenantId, returnUrl } = body;

    if (!tenantId) {
      return new Response(JSON.stringify({ error: 'Missing tenantId' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    const subs = await options.subscriptionRepo.getByTenantId(tenantId);
    const activeSub = subs.find((s) => s.status === 'active' && s.stripeCustomerId);

    if (!activeSub) {
      return new Response(JSON.stringify({ error: 'No active subscription found for tenant' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    const session = await options.stripeService.createCustomerPortalSession({
      customerId: activeSub.stripeCustomerId,
      returnUrl: returnUrl || 'https://rewilt.com/dashboard'
    });

    return new Response(JSON.stringify({ portalUrl: session.portalUrl }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (err: unknown) {
    return new Response(JSON.stringify({ error: (err as Error).message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
