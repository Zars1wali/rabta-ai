import type { OnboardingService } from '@salesops/core';

export interface OnboardingRouteOptions {
  onboardingService: OnboardingService;
}

export async function handleOnboardingVerifyRoute(
  req: Request,
  options: OnboardingRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await req.json();
    const { sourceKind, sourceConfig } = body;

    if (!sourceKind || !sourceConfig) {
      return new Response(
        JSON.stringify({ error: 'sourceKind and sourceConfig are required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const result = await options.onboardingService.verifySource(sourceKind, sourceConfig);

    return new Response(JSON.stringify(result), {
      status: result.ok ? 200 : 400,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (err: unknown) {
    return new Response(JSON.stringify({ error: (err as Error).message }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

export async function handleOnboardingProvisionRoute(
  req: Request,
  options: OnboardingRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const draft = await req.json();
    const result = await options.onboardingService.provisionTenant(draft);

    if (!result.ok) {
      return new Response(
        JSON.stringify({ error: result.error, issues: result.issues }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response(JSON.stringify(result), {
      status: 201,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (err: unknown) {
    return new Response(JSON.stringify({ error: (err as Error).message }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
