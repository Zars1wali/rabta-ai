import type { TenantAdminService } from '@salesops/core';

export interface AdminRouteOptions {
  adminService: TenantAdminService;
  adminApiKey?: string;
}

function verifyAdminAuth(req: Request, expectedKey?: string): boolean {
  const adminKey = expectedKey || process.env.ADMIN_API_KEY || 'salesops_admin_secret_key';
  const provided = req.headers.get('x-admin-key') || req.headers.get('authorization')?.replace(/^Bearer\s+/i, '');
  return provided === adminKey;
}

export async function handleAdminTenantGetRoute(
  req: Request,
  options: AdminRouteOptions,
  tenantId: string
): Promise<Response> {
  if (!verifyAdminAuth(req, options.adminApiKey)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const result = await options.adminService.getTenant(tenantId);
  if (!result.ok) {
    return new Response(JSON.stringify({ error: result.error }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  return new Response(JSON.stringify(result.tenant), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

export async function handleAdminTenantCreateRoute(
  req: Request,
  options: AdminRouteOptions
): Promise<Response> {
  if (!verifyAdminAuth(req, options.adminApiKey)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await req.json();
    const result = await options.adminService.createTenant(body);

    if (!result.ok) {
      return new Response(
        JSON.stringify({ error: result.error, issues: result.issues }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    return new Response(JSON.stringify(result.tenant), {
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

export async function handleAdminTenantUpdateRoute(
  req: Request,
  options: AdminRouteOptions,
  tenantId: string
): Promise<Response> {
  if (!verifyAdminAuth(req, options.adminApiKey)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (req.method !== 'PUT' && req.method !== 'PATCH') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  try {
    const body = await req.json();
    const result = await options.adminService.updateTenantConfig({
      tenantId,
      config: body.config,
      displayName: body.displayName,
      expectedVersion: body.expectedVersion
    });

    if (!result.ok) {
      const isConflict = result.error?.includes('Conflict');
      return new Response(
        JSON.stringify({ error: result.error, issues: result.issues }),
        {
          status: isConflict ? 409 : 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    return new Response(JSON.stringify(result.tenant), {
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
