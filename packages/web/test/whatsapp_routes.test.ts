import { describe, it, expect, vi } from 'vitest';
import crypto from 'node:crypto';
import {
  handleWhatsAppGetRoute,
  handleWhatsAppPostRoute
} from '../src/server/index.js';
import type {
  WhatsAppCloudClient,
  AgentTurnExecutor,
  SessionRepository
} from '@salesops/core';
import { REWILT_TENANT_ID } from '@salesops/core';

describe('WhatsApp Webhook Routes (WP-19)', () => {
  const tenantId = REWILT_TENANT_ID;
  const appSecret = 'test_secret_777';
  const verifyToken = 'test_verify_token_123';

  const mockWhatsAppClient = {
    verifyWebhookChallenge: vi.fn().mockImplementation((mode, token, challenge, expected) => {
      if (mode === 'subscribe' && token === expected) return challenge;
      return null;
    }),
    verifyWebhookSignature: vi.fn().mockImplementation((rawBody, signature, secret) => {
      if (!signature) return false;
      const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
      return signature.replace(/^sha256=/i, '') === expected;
    }),
    parseInboundWebhookPayload: vi.fn().mockReturnValue([
      {
        messageId: 'wam_in_1',
        from: '351912345678',
        text: 'Qual o preço do plano Standard?',
        timestamp: new Date().toISOString(),
        type: 'text'
      }
    ]),
    sendTextMessage: vi.fn().mockResolvedValue({ ok: true, messageId: 'wam_out_1' })
  } as unknown as WhatsAppCloudClient;

  const mockTurnExecutor = {
    executeTurn: vi.fn().mockResolvedValue({
      chunks: ['O plano Standard custa 79.00 EUR por mês.'],
      stage: 'present',
      toolCalls: [],
      events: []
    })
  } as unknown as AgentTurnExecutor;

  const mockSessionRepo = {
    getSession: vi.fn().mockResolvedValue(null),
    createSession: vi.fn().mockImplementation(async (data) => ({ ...data, createdAt: new Date() }))
  } as unknown as SessionRepository;

  it('handles GET webhook challenge verification', async () => {
    const req = new Request(
      `http://localhost/api/salesops/channels/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=${verifyToken}&hub.challenge=1158201444`
    );

    const res = await handleWhatsAppGetRoute(req, {
      verifyToken,
      whatsappClient: mockWhatsAppClient
    });

    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toBe('1158201444');
  });

  it('handles POST inbound webhook, verifies signature, executes turn, and sends reply bubbles', async () => {
    const payload = JSON.stringify({
      object: 'whatsapp_business_account',
      entry: [{ id: '123', changes: [] }]
    });

    const hmac = crypto.createHmac('sha256', appSecret).update(payload).digest('hex');

    const req = new Request('http://localhost/api/salesops/channels/whatsapp/webhook', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-hub-signature-256': `sha256=${hmac}`
      },
      body: payload
    });

    const res = await handleWhatsAppPostRoute(req, {
      verifyToken,
      appSecret,
      tenantId,
      whatsappClient: mockWhatsAppClient,
      turnExecutor: mockTurnExecutor,
      sessionRepo: mockSessionRepo
    });

    expect(res.status).toBe(200);
    expect(mockTurnExecutor.executeTurn).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantId,
        message: expect.objectContaining({ content: 'Qual o preço do plano Standard?' })
      })
    );
    expect(mockWhatsAppClient.sendTextMessage).toHaveBeenCalledWith(
      '351912345678',
      expect.stringContaining('79.00 EUR')
    );
  });
});
