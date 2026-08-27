import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    return NextResponse.json({
      ok: true,
      leadId: `lead_${crypto.randomUUID().slice(0, 8)}`,
      receivedAt: new Date().toISOString(),
      data: body
    });
  } catch {
    return NextResponse.json({ ok: false, error: 'Invalid lead payload' }, { status: 400 });
  }
}
