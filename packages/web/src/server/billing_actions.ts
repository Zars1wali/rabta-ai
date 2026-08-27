import type { StripeBillingService } from '@salesops/core';

export interface BillingActionsRouteOptions {
  billingService: StripeBillingService;
}

export async function handleTopUpCheckoutRoute(
  req: Request,
  options: BillingActionsRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await req.json();
    const { tenantId, blockCount, email } = body;

    if (!tenantId) {
      return new Response(JSON.stringify({ error: 'tenantId is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    const result = await options.billingService.createTopUpCheckoutSession({
      tenantId,
      blockCount: blockCount || 1,
      email
    });

    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (err: unknown) {
    return new Response(JSON.stringify({ error: (err as Error).message }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
