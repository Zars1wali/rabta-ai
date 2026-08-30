import type {
  WhatsAppCloudClient,
  AgentTurnExecutor,
  SessionRepository,
  TenantRepository,
  WhatsAppMessageQueue
} from '@salesops/core';
import {
  chunkReplyForWhatsApp,
  OwnerControlPlane,
  parseOwnerCommand
} from '@salesops/core';

export interface WhatsAppRouteOptions {
  verifyToken: string;
  appSecret: string;
  tenantId: string;
  whatsappClient: WhatsAppCloudClient;
  turnExecutor?: AgentTurnExecutor;
  sessionRepo?: SessionRepository;
  tenantRepo?: TenantRepository;
  ownerControlPlane?: OwnerControlPlane;
  queue?: WhatsAppMessageQueue;
}

export async function handleWhatsAppGetRoute(
  req: Request,
  options: { verifyToken: string; whatsappClient: WhatsAppCloudClient }
): Promise<Response> {
  const url = new URL(req.url);
  const mode = url.searchParams.get('hub.mode');
  const token = url.searchParams.get('hub.verify_token');
  const challenge = url.searchParams.get('hub.challenge');

  const verified = options.whatsappClient.verifyWebhookChallenge(
    mode,
    token,
    challenge,
    options.verifyToken
  );

  if (verified) {
    return new Response(verified, { status: 200, headers: { 'Content-Type': 'text/plain' } });
  }

  return new Response('Forbidden', { status: 403 });
}

export async function handleWhatsAppPostRoute(
  req: Request,
  options: WhatsAppRouteOptions
): Promise<Response> {
  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  const rawBody = await req.text();
  const signature = req.headers.get('x-hub-signature-256');

  // 1. Verify HMAC-SHA256 signature
  const isValidSignature = options.whatsappClient.verifyWebhookSignature(
    rawBody,
    signature,
    options.appSecret
  );

  if (!isValidSignature) {
    return new Response('Invalid Signature', { status: 401 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return new Response('Invalid JSON', { status: 400 });
  }

  // 2. High-Throughput Async Queue Pipeline (< 100ms response)
  if (options.queue) {
    const jobId = await options.queue.enqueue({
      tenantId: options.tenantId,
      rawPayload: payload,
      receivedAt: new Date().toISOString(),
      signature: signature || undefined
    });

    return new Response(JSON.stringify({ status: 'queued', jobId }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'X-Response-Time': 'async-queued'
      }
    });
  }

  // 3. Fallback synchronous path for direct callers
  const inboundMessages = options.whatsappClient.parseInboundWebhookPayload(payload);
  const controlPlane = options.ownerControlPlane || new OwnerControlPlane();

  for (const msg of inboundMessages) {
    // Check if message is a merchant owner slash command
    const ownerCmd = parseOwnerCommand(msg.text);
    if (ownerCmd && options.tenantRepo && options.sessionRepo) {
      const tenant = await options.tenantRepo.getById(options.tenantId);
      if (tenant && controlPlane.isOwnerPhone(tenant.config, msg.from)) {
        const cmdResult = await controlPlane.executeCommand({
          command: ownerCmd,
          tenantConfig: tenant.config,
          sessionRepo: options.sessionRepo,
          tenantRepo: options.tenantRepo
        });

        await options.whatsappClient.sendTextMessage(msg.from, cmdResult.replyText);
        continue;
      }
    }

    if (options.sessionRepo && options.turnExecutor) {
      let session = await options.sessionRepo.getSession(options.tenantId, `wa_${msg.from}`);
      const sessionId = session?.id || crypto.randomUUID();

      if (!session) {
        session = await options.sessionRepo.createSession({
          id: sessionId,
          tenantId: options.tenantId,
          channel: 'whatsapp',
          stage: 'greet',
          externalRef: msg.from
        });
      } else if (session.stage === 'handoff') {
        continue;
      }

      const turnResult = await options.turnExecutor.executeTurn({
        tenantId: options.tenantId,
        sessionId,
        message: {
          id: msg.messageId || crypto.randomUUID(),
          channel: 'whatsapp',
          sessionId,
          senderId: msg.from,
          content: msg.text,
          timestamp: msg.timestamp || new Date().toISOString()
        },
        history: [],
        stage: (session?.stage as 'greet') || 'greet',
        locale: session?.locale || 'pt-PT'
      });

      const replyText = turnResult.chunks.join('\n\n');
      if (replyText) {
        const { bubbles } = chunkReplyForWhatsApp(replyText);
        for (const bubble of bubbles) {
          await options.whatsappClient.sendTextMessage(msg.from, bubble);
        }
      }
    }
  }

  return new Response(JSON.stringify({ status: 'ok' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}
