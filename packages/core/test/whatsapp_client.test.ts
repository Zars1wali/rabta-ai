import { describe, it, expect, vi } from 'vitest';
import crypto from 'node:crypto';
import { WhatsAppCloudClient } from '../src/channels/index.js';

describe('WhatsApp Cloud API Client (WP-19)', () => {
  const client = new WhatsAppCloudClient({
    accessToken: 'test_token_123',
    phoneNumberId: 'phone_id_999'
  });

  it('verifies Meta webhook challenge when token matches', () => {
    const challenge = client.verifyWebhookChallenge(
      'subscribe',
      'secret_verify_token',
      '1158201444',
      'secret_verify_token'
    );
    expect(challenge).toBe('1158201444');

    const invalid = client.verifyWebhookChallenge(
      'subscribe',
      'wrong_token',
      '1158201444',
      'secret_verify_token'
    );
    expect(invalid).toBeNull();
  });

  it('verifies x-hub-signature-256 HMAC-SHA256 signature', () => {
    const appSecret = 'meta_app_secret_xyz';
    const payload = JSON.stringify({ object: 'whatsapp_business_account' });
    const hmac = crypto.createHmac('sha256', appSecret).update(payload).digest('hex');
    const signatureHeader = `sha256=${hmac}`;

    const isValid = client.verifyWebhookSignature(payload, signatureHeader, appSecret);
    expect(isValid).toBe(true);

    const isInvalid = client.verifyWebhookSignature(payload, 'sha256=invalid_sig', appSecret);
    expect(isInvalid).toBe(false);
  });

  it('parses inbound text and interactive button webhook payloads', () => {
    const metaPayload = {
      object: 'whatsapp_business_account',
      entry: [
        {
          id: 'WHATSAPP_BUSINESS_ACCOUNT_ID',
          changes: [
            {
              value: {
                messaging_product: 'whatsapp',
                metadata: { display_phone_number: '351912345678', phone_number_id: 'phone_id_999' },
                messages: [
                  {
                    from: '351912345678',
                    id: 'wamid.HBgLMzUxOTEyMzQ1Njc4FQIAEhggM0E2OTM1MzAyRkEzOTYw',
                    timestamp: '1724760000',
                    text: { body: 'Qual o valor do plano Standard?' },
                    type: 'text'
                  },
                  {
                    from: '351912345678',
                    id: 'wamid.HBgLMzUxOTEyMzQ1Njc4FQIAEhggM0E2OTM1MzAyRkEzOTYx',
                    timestamp: '1724760005',
                    interactive: {
                      type: 'button_reply',
                      button_reply: { id: 'btn_quote_std', title: 'Pedir Orçamento' }
                    },
                    type: 'interactive'
                  }
                ]
              },
              field: 'messages'
            }
          ]
        }
      ]
    };

    const messages = client.parseInboundWebhookPayload(metaPayload);
    expect(messages.length).toBe(2);

    expect(messages[0]?.from).toBe('351912345678');
    expect(messages[0]?.text).toBe('Qual o valor do plano Standard?');
    expect(messages[0]?.type).toBe('text');

    expect(messages[1]?.from).toBe('351912345678');
    expect(messages[1]?.text).toBe('Pedir Orçamento');
    expect(messages[1]?.type).toBe('button_reply');
    expect(messages[1]?.buttonPayload).toBe('btn_quote_std');
  });

  it('sends text message via Graph API', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        messaging_product: 'whatsapp',
        contacts: [{ input: '351912345678', wa_id: '351912345678' }],
        messages: [{ id: 'wamid.outbound_123' }]
      })
    });

    const customClient = new WhatsAppCloudClient({
      accessToken: 'token_123',
      phoneNumberId: 'phone_999',
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await customClient.sendTextMessage('351912345678', 'Olá! Como posso ajudar?');
    expect(res.ok).toBe(true);
    expect(res.messageId).toBe('wamid.outbound_123');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('https://graph.facebook.com/v21.0/phone_999/messages'),
      expect.objectContaining({
        method: 'POST',
        headers: {
          Authorization: 'Bearer token_123',
          'Content-Type': 'application/json'
        }
      })
    );
  });
});
