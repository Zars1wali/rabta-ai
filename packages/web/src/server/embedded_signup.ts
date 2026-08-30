import { MetaEmbeddedSignupService } from '@salesops/core';
import type { ChannelRepository } from '@salesops/core';

export interface EmbeddedSignupRouteOptions {
  service?: MetaEmbeddedSignupService;
  channelRepo?: ChannelRepository;
  defaultTenantId?: string;
}

export async function handleEmbeddedSignupConfigRoute(
  req: Request,
  options?: EmbeddedSignupRouteOptions
): Promise<Response> {
  const service = options?.service || new MetaEmbeddedSignupService();
  const url = new URL(req.url);
  const tenantId = url.searchParams.get('tenantId') || options?.defaultTenantId || 'default';

  const config = service.getFrontendConfig(tenantId);
  return new Response(JSON.stringify(config), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

export async function handleEmbeddedSignupCallbackRoute(
  req: Request,
  options?: EmbeddedSignupRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  let body: { code?: string; tenantId?: string; wabaId?: string; phoneNumberId?: string };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ ok: false, error: 'Invalid JSON body' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (!body.code) {
    return new Response(JSON.stringify({ ok: false, error: 'OAuth "code" is required.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const service = options?.service || new MetaEmbeddedSignupService();
  const result = await service.exchangeCodeAndProvisionWaba({
    code: body.code,
    wabaId: body.wabaId,
    phoneNumberId: body.phoneNumberId
  });

  if (!result.ok) {
    return new Response(JSON.stringify(result), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Provision channel in database if channelRepo is supplied
  if (options?.channelRepo && (body.tenantId || options.defaultTenantId)) {
    const tenantId = body.tenantId || options.defaultTenantId!;
    try {
      await options.channelRepo.createChannel({
        tenantId,
        type: 'whatsapp',
        wabaId: result.wabaId,
        phoneNumberId: result.phoneNumberId,
        displayNumber: result.displayPhoneNumber,
        status: 'active',
        tokenRef: result.accessToken
      });
    } catch {
      // ignore insert conflict
    }
  }

  return new Response(JSON.stringify(result), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}
