import { NextResponse } from 'next/server';
import { ZPI_TENANT_ID, ZPI_TENANT_CONFIG } from '@salesops/core';

export async function POST(req: Request) {
  let locale = 'en';
  try {
    const body = await req.json();
    if (body.locale) locale = body.locale;
  } catch {
    // Empty body fallback
  }

  const sessionId = crypto.randomUUID();
  const greeting = ZPI_TENANT_CONFIG.persona.greeting;

  return NextResponse.json({
    ok: true,
    sessionId,
    tenantId: ZPI_TENANT_ID,
    greeting,
    stage: 'greet',
    locale
  });
}
