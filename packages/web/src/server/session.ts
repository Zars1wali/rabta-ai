import { z } from 'zod';
import type {
  SessionRepository,
  MessageRepository,
  TenantRepository
} from '@salesops/core';
import type { TenantConfig } from '@salesops/types';
import { resolveTenantByOrigin, type TenantRecord } from './tenant_resolver.js';

export const CreateSessionBodySchema = z.object({
  locale: z.string().default('pt-PT'),
  externalRef: z.string().nullable().optional()
});
export type CreateSessionBody = z.infer<typeof CreateSessionBodySchema>;

export interface SessionRouteContext {
  tenantRepo: TenantRepository;
  sessionRepo: SessionRepository;
  messageRepo: MessageRepository;
  allTenantsProvider?: () => Promise<TenantRecord[]>;
}

export async function handleSessionRoute(req: Request, ctx: SessionRouteContext): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method Not Allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const originHeader = req.headers.get('origin') || req.headers.get('referer');
  const resolution = await resolveTenantByOrigin(originHeader, ctx.tenantRepo, ctx.allTenantsProvider);

  if (!resolution.ok || !resolution.tenant) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: resolution.error || 'Origin not authorized for any active tenant.'
      }),
      {
        status: resolution.statusCode || 403,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }

  const tenant = resolution.tenant;
  const tenantConfig = tenant.config as TenantConfig;

  let bodyData: CreateSessionBody = { locale: 'pt-PT' };
  try {
    const rawBody = await req.json();
    const parsed = CreateSessionBodySchema.safeParse(rawBody);
    if (parsed.success) {
      bodyData = parsed.data;
    }
  } catch {
    // Empty body is acceptable; defaults to pt-PT
  }

  // 1. Create session
  const session = await ctx.sessionRepo.createSession({
    tenantId: tenant.id,
    channel: 'web',
    externalRef: bodyData.externalRef ?? null,
    stage: 'greet',
    locale: bodyData.locale
  });

  // 2. Build initial greeting with EU AI Act Art. 50 disclosure
  const customGreeting = tenantConfig.persona?.greeting;
  const baseGreeting =
    customGreeting ||
    `Olá! Sou o assistente de IA da ${tenant.displayName}. Como posso ajudar hoje?`;

  // 3. Persist initial greeting message
  await ctx.messageRepo.addMessage({
    tenantId: tenant.id,
    sessionId: session.id,
    role: 'agent',
    content: baseGreeting
  });

  return new Response(
    JSON.stringify({
      ok: true,
      sessionId: session.id,
      tenantId: tenant.id,
      greeting: baseGreeting,
      stage: session.stage,
      locale: session.locale
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }
  );
}
