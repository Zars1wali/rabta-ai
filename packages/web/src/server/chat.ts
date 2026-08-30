import { z } from 'zod';
import type { AgentTurnExecutor, SessionRepository, MessageRepository } from '@salesops/core';
import type { AgentTurnInput, FunnelStage } from '@salesops/types';

export const ChatRequestBodySchema = z.object({
  sessionId: z.string().uuid('sessionId must be a valid UUID'),
  tenantId: z.string().uuid().optional(),
  message: z.object({
    content: z.string().min(1, 'Message content cannot be empty'),
    mediaUrl: z.string().url().nullable().optional()
  }),
  locale: z.string().optional()
});
export type ChatRequestBody = z.infer<typeof ChatRequestBodySchema>;

export interface ChatRouteContext {
  executor: AgentTurnExecutor;
  sessionRepo: SessionRepository;
  messageRepo?: MessageRepository;
}

export async function handleChatRoute(req: Request, ctx: ChatRouteContext): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method Not Allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  let body: ChatRequestBody;
  try {
    const rawBody = await req.json();
    body = ChatRequestBodySchema.parse(rawBody);
  } catch (err: unknown) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: `Invalid chat request: ${(err as Error).message}`
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }

  // 1. Resolve session to get verified tenantId and current stage (IDOR protection)
  const tenantIdCandidate = body.tenantId || '00000000-0000-4000-8000-000000000001';
  const session = await ctx.sessionRepo.getSession(tenantIdCandidate, body.sessionId);
  if (!session) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: 'Session not found for the provided tenant.'
      }),
      {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }

  const tenantId = session.tenantId;
  const currentStage: FunnelStage = (session.stage as FunnelStage) || 'discover';
  const sessionLocale = body.locale || session.locale || 'pt-PT';

  const history = ctx.messageRepo
    ? await ctx.messageRepo.getRecentHistory(tenantId, session.id, 15)
    : [];

  const turnInput: AgentTurnInput = {
    sessionId: session.id,
    tenantId,
    message: {
      id: crypto.randomUUID(),
      channel: (session.channel as 'web' | 'whatsapp' | 'email') || 'web',
      sessionId: session.id,
      senderId: 'visitor',
      content: body.message.content,
      mediaUrl: body.message.mediaUrl ?? null,
      timestamp: new Date().toISOString()
    },
    history,
    stage: currentStage,
    locale: sessionLocale
  };

  // 2. Execute turn via agent runtime
  let output;
  try {
    output = await ctx.executor.executeTurn(turnInput);
  } catch (err: unknown) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: `Turn execution failed: ${(err as Error).message}`
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }

  // 3. Create SSE stream response
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      // Stream tokens / chunks
      for (const chunk of output.chunks) {
        const words = chunk.split(' ');
        for (let i = 0; i < words.length; i++) {
          const wordWithSpace = i === words.length - 1 ? words[i]! : `${words[i]} `;
          const sseToken = `event: token\ndata: ${JSON.stringify({ text: wordWithSpace })}\n\n`;
          controller.enqueue(encoder.encode(sseToken));
        }
      }

      // Stream events (e.g. checkout_url, handoff)
      for (const event of output.events) {
        const sseEvent = `event: event\ndata: ${JSON.stringify(event)}\n\n`;
        controller.enqueue(encoder.encode(sseEvent));
      }

      // Stream completion done frame
      const sseDone = `event: done\ndata: ${JSON.stringify({
        stage: output.stage,
        toolCalls: output.toolCalls,
        usage: output.usage
      })}\n\n`;
      controller.enqueue(encoder.encode(sseDone));

      controller.close();
    }
  });

  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive'
    }
  });
}
