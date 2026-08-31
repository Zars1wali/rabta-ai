import { describe, it, expect, vi, beforeEach } from 'vitest';
import crypto from 'node:crypto';
import {
  WhatsAppCloudClient,
  WhatsAppMessageProcessor,
  type VoiceTranscriber
} from '../src/channels/index.js';
import type { AgentTurnExecutor } from '../src/turn/loop.js';

describe('Milestone 3: WhatsApp Cloud API Ingress & 24-Hour Service Window Engine', () => {
  const TENANT_ID = '11111111-1111-4111-8111-111111111111';
  const APP_SECRET = 'meta_test_app_secret_xyz123';
  const VERIFY_TOKEN = 'meta_test_verify_token_456';

  let mockClient: WhatsAppCloudClient;
  let mockTurnExecutor: AgentTurnExecutor;
  let mockContactRepo: any;
  let mockConversationRepo: any;
  let mockMessageRepo: any;
  let mockSessionRepo: any;
  let mockTenantRepo: any;

  beforeEach(() => {
    mockClient = new WhatsAppCloudClient({
      accessToken: 'test_token',
      phoneNumberId: '123456789'
    });

    mockTurnExecutor = {
      executeTurn: vi.fn().mockResolvedValue({
        chunks: ['Grüezi! Gerne erstelle ich Ihnen eine Offerte für die Endreinigung.'],
        stage: 'qualify',
        toolCalls: [],
        events: [],
        usage: { inputTokens: 100, outputTokens: 50, costMinor: 1 }
      })
    } as unknown as AgentTurnExecutor;

    const contactsStore = new Map<string, any>();
    mockContactRepo = {
      upsertContact: vi.fn().mockImplementation(async (data) => {
        const contact = {
          id: 'contact_001',
          tenantId: data.tenantId,
          waId: data.waId,
          phoneE164: data.phoneE164,
          language: 'de',
          consentAt: data.consentAt || new Date(),
          createdAt: new Date(),
          updatedAt: new Date()
        };
        contactsStore.set(data.waId, contact);
        return contact;
      })
    };

    const conversationsStore = new Map<string, any>();
    mockConversationRepo = {
      getOpenConversationByContact: vi.fn().mockImplementation(async (_tenantId, contactId) => {
        return conversationsStore.get(contactId) || null;
      }),
      createConversation: vi.fn().mockImplementation(async (data) => {
        const conv = {
          id: 'conv_001',
          ...data,
          lastMessageAt: new Date(),
          createdAt: new Date()
        };
        conversationsStore.set(data.contactId, conv);
        return conv;
      }),
      updateServiceWindow: vi.fn().mockImplementation(async (convId, expiresAt) => {
        for (const [key, conv] of conversationsStore.entries()) {
          if (conv.id === convId) {
            conv.serviceWindowExpiresAt = expiresAt;
            conversationsStore.set(key, conv);
            return conv;
          }
        }
        return null;
      })
    };

    const messagesStore = new Map<string, any>();
    mockMessageRepo = {
      getMessageByWamid: vi.fn().mockImplementation(async (wamid: string) => {
        return messagesStore.get(wamid) || null;
      }),
      addMessage: vi.fn().mockImplementation(async (data) => {
        const msg = { id: `msg_${Date.now()}_${Math.random()}`, ...data, createdAt: new Date() };
        if (data.wamid) {
          messagesStore.set(data.wamid, msg);
        }
        return msg;
      })
    };

    mockSessionRepo = {
      getSession: vi.fn().mockResolvedValue(null),
      createSession: vi.fn().mockResolvedValue({ id: 'session_001', stage: 'greet' })
    };

    mockTenantRepo = {
      getById: vi.fn().mockResolvedValue({
        id: TENANT_ID,
        slug: 'swiss-clean',
        config: { ownerPhone: '+41790000000' }
      })
    };
  });

  describe('1. Thin Webhook Ingress & HMAC-SHA256 Verification', () => {
    it('verifies Meta challenge during GET subscription verification', () => {
      const challenge = mockClient.verifyWebhookChallenge('subscribe', VERIFY_TOKEN, 'CHALLENGE_CODE_123', VERIFY_TOKEN);
      expect(challenge).toBe('CHALLENGE_CODE_123');

      const invalid = mockClient.verifyWebhookChallenge('subscribe', 'wrong_token', 'CHALLENGE_CODE_123', VERIFY_TOKEN);
      expect(invalid).toBeNull();
    });

    it('verifies valid HMAC-SHA256 signature on raw webhook body and rejects tampered bodies', () => {
      const rawPayload = JSON.stringify({ entry: [{ changes: [] }] });
      const validSignature = 'sha256=' + crypto.createHmac('sha256', APP_SECRET).update(rawPayload).digest('hex');

      const isVerified = mockClient.verifyWebhookSignature(rawPayload, validSignature, APP_SECRET);
      expect(isVerified).toBe(true);

      const isTampered = mockClient.verifyWebhookSignature(rawPayload + 'tampered', validSignature, APP_SECRET);
      expect(isTampered).toBe(false);
    });
  });

  describe('2. wamid Idempotency & Queue Processing Engine', () => {
    it('deduplicates re-delivered WhatsApp webhook messages and prevents duplicate AI turns', async () => {
      const processor = new WhatsAppMessageProcessor({
        whatsappClient: mockClient,
        turnExecutor: mockTurnExecutor,
        contactRepo: mockContactRepo,
        conversationRepo: mockConversationRepo,
        messageRepo: mockMessageRepo,
        sessionRepo: mockSessionRepo,
        tenantRepo: mockTenantRepo
      });

      const sendTextSpy = vi.spyOn(mockClient, 'sendTextMessage').mockResolvedValue({ ok: true, messageId: 'out_wamid_001' });

      const wamid = 'wamid.HBgLMjUxOTg3NjU0MzIxFQIAEhggQ0RFRjAxMjM0NTY3ODkwQUJDREVGMDEyMzQ1Njc4OTA=';
      const webhookPayload = {
        entry: [
          {
            changes: [
              {
                value: {
                  messages: [
                    {
                      id: wamid,
                      from: '41791234567',
                      timestamp: `${Math.floor(Date.now() / 1000)}`,
                      type: 'text',
                      text: { body: 'Grüezi! Was kostet eine 4.5 Zimmer Endreinigung?' }
                    }
                  ]
                }
              }
            ]
          }
        ]
      };

      // First Delivery: should be processed
      const firstResult = await processor.processJob({
        jobId: 'job_1',
        tenantId: TENANT_ID,
        rawPayload: webhookPayload,
        receivedAt: new Date().toISOString()
      });

      expect(firstResult.processedCount).toBe(1);
      expect(firstResult.duplicateCount).toBe(0);
      expect(mockTurnExecutor.executeTurn).toHaveBeenCalledTimes(1);
      expect(sendTextSpy).toHaveBeenCalledTimes(1);

      // Second Delivery (Meta Retry with identical wamid): should be skipped
      const secondResult = await processor.processJob({
        jobId: 'job_2',
        tenantId: TENANT_ID,
        rawPayload: webhookPayload,
        receivedAt: new Date().toISOString()
      });

      expect(secondResult.processedCount).toBe(0);
      expect(secondResult.duplicateCount).toBe(1);
      // Turn executor and outbound client should NOT have been called a second time
      expect(mockTurnExecutor.executeTurn).toHaveBeenCalledTimes(1);
      expect(sendTextSpy).toHaveBeenCalledTimes(1);
    });
  });

  describe('3. 24-Hour Customer Service Window Guard', () => {
    it('allows freeform conversational text when within the 24-hour window', async () => {
      const processor = new WhatsAppMessageProcessor({
        whatsappClient: mockClient,
        turnExecutor: mockTurnExecutor,
        contactRepo: mockContactRepo,
        conversationRepo: mockConversationRepo,
        messageRepo: mockMessageRepo,
        sessionRepo: mockSessionRepo,
        tenantRepo: mockTenantRepo
      });

      const sendTextSpy = vi.spyOn(mockClient, 'sendTextMessage').mockResolvedValue({ ok: true, messageId: 'out_wamid_002' });
      const sendTemplateSpy = vi.spyOn(mockClient, 'sendTemplateMessage').mockResolvedValue({ ok: true, messageId: 'out_wamid_tmpl' });

      // Inbound message sent right now
      const webhookPayload = {
        entry: [
          {
            changes: [
              {
                value: {
                  messages: [
                    {
                      id: 'wamid_fresh_001',
                      from: '41791234567',
                      timestamp: `${Math.floor(Date.now() / 1000)}`,
                      type: 'text',
                      text: { body: 'Hallo' }
                    }
                  ]
                }
              }
            ]
          }
        ]
      };

      await processor.processJob({
        jobId: 'job_fresh',
        tenantId: TENANT_ID,
        rawPayload: webhookPayload,
        receivedAt: new Date().toISOString()
      });

      expect(sendTextSpy).toHaveBeenCalled();
      expect(sendTemplateSpy).not.toHaveBeenCalled();
    });

    it('blocks freeform text and triggers approved Template Message fallback when outside 24-hour window', async () => {
      const processor = new WhatsAppMessageProcessor({
        whatsappClient: mockClient,
        turnExecutor: mockTurnExecutor,
        contactRepo: mockContactRepo,
        conversationRepo: mockConversationRepo,
        messageRepo: mockMessageRepo,
        sessionRepo: mockSessionRepo,
        tenantRepo: mockTenantRepo,
        fallbackTemplateName: 'service_window_reengage_de'
      });

      const sendTextSpy = vi.spyOn(mockClient, 'sendTextMessage').mockResolvedValue({ ok: true });
      const sendTemplateSpy = vi.spyOn(mockClient, 'sendTemplateMessage').mockResolvedValue({ ok: true, messageId: 'out_wamid_tmpl_001' });

      // Inbound timestamp from 48 hours ago (expired customer service window)
      const expiredTimestamp = Math.floor(Date.now() / 1000) - 48 * 3600;
      const webhookPayload = {
        entry: [
          {
            changes: [
              {
                value: {
                  messages: [
                    {
                      id: 'wamid_expired_001',
                      from: '41791234567',
                      timestamp: `${expiredTimestamp}`,
                      type: 'text',
                      text: { body: 'Später nachgefragt' }
                    }
                  ]
                }
              }
            ]
          }
        ]
      };

      await processor.processJob({
        jobId: 'job_expired',
        tenantId: TENANT_ID,
        rawPayload: webhookPayload,
        receivedAt: new Date().toISOString()
      });

      // Freeform message must be BLOCKED
      expect(sendTextSpy).not.toHaveBeenCalled();
      // Approved Meta template must be sent instead
      expect(sendTemplateSpy).toHaveBeenCalledWith(
        '41791234567',
        'service_window_reengage_de',
        'de',
        expect.any(Array)
      );
    });
  });

  describe('4. Multimodal Voice Note / Audio Ingress Pipeline', () => {
    it('downloads audio media and transcribes Swiss German voice notes into text', async () => {
      const mockVoiceTranscriber: VoiceTranscriber = {
        transcribeAudio: vi.fn().mockResolvedValue({
          text: 'Grüezi miteinand, ich bruuche e Reinigungs-Offerte für mini 3.5 Zimmer Wohnig in Winterthur.',
          language: 'de'
        })
      };

      const processor = new WhatsAppMessageProcessor({
        whatsappClient: mockClient,
        turnExecutor: mockTurnExecutor,
        contactRepo: mockContactRepo,
        conversationRepo: mockConversationRepo,
        messageRepo: mockMessageRepo,
        sessionRepo: mockSessionRepo,
        tenantRepo: mockTenantRepo,
        voiceTranscriber: mockVoiceTranscriber
      });

      vi.spyOn(mockClient, 'downloadMedia').mockResolvedValue({
        buffer: Buffer.from('mock_ogg_opus_audio_bytes'),
        mimeType: 'audio/ogg; codecs=opus'
      });
      vi.spyOn(mockClient, 'sendTextMessage').mockResolvedValue({ ok: true, messageId: 'out_wamid_voice_reply' });

      const audioWebhookPayload = {
        entry: [
          {
            changes: [
              {
                value: {
                  messages: [
                    {
                      id: 'wamid_audio_001',
                      from: '41791234567',
                      timestamp: `${Math.floor(Date.now() / 1000)}`,
                      type: 'audio',
                      audio: {
                        id: 'media_audio_id_999',
                        mime_type: 'audio/ogg; codecs=opus'
                      }
                    }
                  ]
                }
              }
            ]
          }
        ]
      };

      await processor.processJob({
        jobId: 'job_audio',
        tenantId: TENANT_ID,
        rawPayload: audioWebhookPayload,
        receivedAt: new Date().toISOString()
      });

      expect(mockVoiceTranscriber.transcribeAudio).toHaveBeenCalled();
      expect(mockTurnExecutor.executeTurn).toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.objectContaining({
            content: 'Grüezi miteinand, ich bruuche e Reinigungs-Offerte für mini 3.5 Zimmer Wohnig in Winterthur.'
          })
        })
      );
    });
  });
});
