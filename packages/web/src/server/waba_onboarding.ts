import type { WabaOnboardingService } from '@salesops/core';

export async function handleWabaRegisterRoute(
  req: Request,
  options: { wabaService: WabaOnboardingService }
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method Not Allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await req.json();
    const { phoneNumberId, pin, accessToken } = body;

    if (!phoneNumberId || !pin) {
      return new Response(JSON.stringify({ error: 'phoneNumberId and pin are required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    const res = await options.wabaService.registerPhoneNumber({
      phoneNumberId,
      pin,
      accessToken
    });

    return new Response(JSON.stringify(res), {
      status: res.ok ? 200 : 400,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (err: unknown) {
    return new Response(JSON.stringify({ error: (err as Error).message }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

export async function handleWabaStatusRoute(
  req: Request,
  options: { wabaService: WabaOnboardingService }
): Promise<Response> {
  const url = new URL(req.url);
  const phoneNumberId = url.searchParams.get('phoneNumberId');
  const accessToken = req.headers.get('authorization')?.replace(/^bearer\s+/i, '');

  if (!phoneNumberId) {
    return new Response(JSON.stringify({ error: 'phoneNumberId parameter is required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const res = await options.wabaService.getPhoneNumberStatus({
    phoneNumberId,
    accessToken: accessToken || undefined
  });

  return new Response(JSON.stringify(res), {
    status: res.ok ? 200 : 400,
    headers: { 'Content-Type': 'application/json' }
  });
}
