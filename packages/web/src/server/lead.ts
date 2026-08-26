import { z } from 'zod';
import type {
  SessionRepository,
  LeadRepository,
  TenantRepository,
  NotificationDispatcher
} from '@salesops/core';

export const LeadCaptureRequestSchema = z.object({
  tenantId: z.string().uuid(),
  sessionId: z.string().uuid(),
  consent: z.boolean().refine((val) => val === true, {
    message: 'Explicit GDPR/privacy consent is required before submitting contact details.'
  }),
  name: z.string().optional(),
  email: z.string().email().optional(),
  phone: z.string().optional(),
  companyUrl: z.string().url().optional(),
  notes: z.string().optional()
});

export interface LeadRouteOptions {
  sessionRepo: SessionRepository;
  leadRepo: LeadRepository;
  tenantRepo: TenantRepository;
  notificationDispatcher?: NotificationDispatcher;
}

export async function handleLeadRoute(
  req: Request,
  options: LeadRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const parseResult = LeadCaptureRequestSchema.safeParse(body);
  if (!parseResult.success) {
    return new Response(
      JSON.stringify({
        error: 'Validation failed',
        issues: parseResult.error.issues
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }

  const data = parseResult.data;

  // 1. Verify tenant exists
  const tenant = await options.tenantRepo.getById(data.tenantId);
  if (!tenant) {
    return new Response(JSON.stringify({ error: 'Tenant not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // 2. Verify session exists & record consent_at timestamp
  const session = await options.sessionRepo.getSession(data.tenantId, data.sessionId);
  if (!session) {
    return new Response(JSON.stringify({ error: 'Session not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const consentTimestamp = session.consentAt || new Date();

  // 3. Persist lead in PostgreSQL
  const lead = await options.leadRepo.createLead({
    tenantId: data.tenantId,
    sessionId: data.sessionId,
    name: data.name ?? null,
    email: data.email ?? null,
    phone: data.phone ?? null,
    companyUrl: data.companyUrl ?? null,
    notes: data.notes ?? null,
    consentAt: consentTimestamp
  });

  // 4. Update session stage to 'close' or 'qualify'
  await options.sessionRepo.updateTurn(data.tenantId, data.sessionId, {
    stage: 'qualify',
    tokensUsed: 0,
    costMinor: 0
  });

  // 5. Dispatch outbound notification asynchronously
  if (options.notificationDispatcher) {
    try {
      await options.notificationDispatcher.dispatch({
        type: 'lead_captured',
        tenantId: data.tenantId,
        sessionId: data.sessionId,
        lead
      });
    } catch {
      // Notification dispatch failures do not block the client response
    }
  }

  return new Response(
    JSON.stringify({
      ok: true,
      leadId: lead.id,
      consentAt: lead.consentAt,
      status: 'recorded'
    }),
    {
      status: 201,
      headers: { 'Content-Type': 'application/json' }
    }
  );
}
