export interface HealthRouteContext {
  dbPing?: () => Promise<boolean>;
}

export async function handleHealthRoute(_req: Request, ctx?: HealthRouteContext): Promise<Response> {
  let dbStatus = 'unconfigured';
  if (ctx?.dbPing) {
    try {
      const ok = await ctx.dbPing();
      dbStatus = ok ? 'connected' : 'error';
    } catch {
      dbStatus = 'error';
    }
  }

  return new Response(
    JSON.stringify({
      status: 'ok',
      timestamp: new Date().toISOString(),
      database: dbStatus,
      uptimeSeconds: process.uptime()
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }
  );
}
