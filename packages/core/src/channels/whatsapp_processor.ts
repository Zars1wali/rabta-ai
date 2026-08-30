import type { WhatsAppCloudClient, InboundWhatsAppMessage } from './whatsapp_client.js';
import { chunkReplyForWhatsApp } from './chunker.js';
import type { WhatsAppJobPayload } from './whatsapp_queue.js';
import type { AgentTurnExecutor } from '../agent/turn_loop.js';
import { OwnerControlPlane, parseOwnerCommand } from './owner_control.js';
import type {
  ContactRepository,
  ConversationRepository,
  CommercialMessageRepository,
  TenantRepository,
  SessionRepository
} from '../db/repositories.js';

export interface VoiceTranscriber {
  transcribeAudio(buffer: Buffer, mimeType?: string): Promise<{ text: string; language?: string }>;
}

export interface WhatsAppProcessorOptions {
  whatsappClient: WhatsAppCloudClient;
  turnExecutor: AgentTurnExecutor;
  contactRepo: ContactRepository;
  conversationRepo: ConversationRepository;
  messageRepo: CommercialMessageRepository;
  sessionRepo: SessionRepository;
  tenantRepo: TenantRepository;
  ownerControlPlane?: OwnerControlPlane;
  voiceTranscriber?: VoiceTranscriber;
  fallbackTemplateName?: string;
  defaultChannelId?: string;
}

export class WhatsAppMessageProcessor {
  private whatsappClient: WhatsAppCloudClient;
  private turnExecutor: AgentTurnExecutor;
  private contactRepo: ContactRepository;
  private conversationRepo: ConversationRepository;
  private messageRepo: CommercialMessageRepository;
  private sessionRepo: SessionRepository;
  private tenantRepo: TenantRepository;
  private ownerControlPlane: OwnerControlPlane;
  private voiceTranscriber?: VoiceTranscriber;
  private fallbackTemplateName: string;
  private defaultChannelId: string;

  constructor(options: WhatsAppProcessorOptions) {
    this.whatsappClient = options.whatsappClient;
    this.turnExecutor = options.turnExecutor;
    this.contactRepo = options.contactRepo;
    this.conversationRepo = options.conversationRepo;
    this.messageRepo = options.messageRepo;
    this.sessionRepo = options.sessionRepo;
    this.tenantRepo = options.tenantRepo;
    this.ownerControlPlane = options.ownerControlPlane || new OwnerControlPlane();
    this.voiceTranscriber = options.voiceTranscriber;
    this.fallbackTemplateName = options.fallbackTemplateName || 'service_window_reengage_de';
    this.defaultChannelId = options.defaultChannelId || '00000000-0000-0000-0000-000000000000';
  }

  /**
   * Processes an enqueued WhatsApp job.
   */
  async processJob(job: WhatsAppJobPayload): Promise<{ processedCount: number; duplicateCount: number }> {
    const inboundMessages = this.whatsappClient.parseInboundWebhookPayload(job.rawPayload);
    let processedCount = 0;
    let duplicateCount = 0;

    for (const msg of inboundMessages) {
      const isDuplicate = await this.isMessageDuplicate(job.tenantId, msg.messageId);
      if (isDuplicate) {
        duplicateCount++;
        continue;
      }

      await this.handleSingleMessage(job.tenantId, msg);
      processedCount++;
    }

    return { processedCount, duplicateCount };
  }

  /**
   * Idempotency Check: Prevents processing identical wamid messages.
   */
  async isMessageDuplicate(tenantId: string, wamid?: string): Promise<boolean> {
    if (!wamid) return false;
    const existing = await this.messageRepo.getMessageByWamid(wamid, tenantId);
    return existing !== null;
  }

  /**
   * Processes a single validated inbound WhatsApp message.
   */
  private async handleSingleMessage(tenantId: string, msg: InboundWhatsAppMessage): Promise<void> {
    const inboundTime = msg.timestamp ? new Date(msg.timestamp) : new Date();
    // 24-Hour Customer Service Window: expires 24h from the customer's inbound message
    const serviceWindowExpiresAt = new Date(inboundTime.getTime() + 24 * 60 * 60 * 1000);

    // 1. Upsert Customer Contact
    const phoneE164 = msg.from.startsWith('+') ? msg.from : `+${msg.from}`;
    const contact = await this.contactRepo.upsertContact({
      tenantId,
      waId: msg.from,
      phoneE164,
      consentSource: 'whatsapp_inbound_optin',
      consentAt: inboundTime
    });

    // 2. Find or Create Active Conversation
    let conversation = await this.conversationRepo.getOpenConversationByContact(tenantId, contact.id);
    if (!conversation) {
      conversation = await this.conversationRepo.createConversation({
        tenantId,
        channelId: this.defaultChannelId,
        contactId: contact.id,
        status: 'open',
        aiMode: 'auto',
        serviceWindowExpiresAt
      });
    } else {
      await this.conversationRepo.updateServiceWindow(conversation.id, serviceWindowExpiresAt, tenantId);
    }

    // 3. Resolve Inbound Message Text (handling audio voice notes if present)
    let messageText = msg.text;
    if (msg.type === 'audio' && msg.mediaId && this.voiceTranscriber) {
      const media = await this.whatsappClient.downloadMedia(msg.mediaId);
      if (media?.buffer) {
        const transcription = await this.voiceTranscriber.transcribeAudio(media.buffer, media.mimeType);
        if (transcription.text) {
          messageText = transcription.text;
        }
      }
    }

    // 4. Record Inbound Message in Ledger
    await this.messageRepo.addMessage({
      tenantId,
      conversationId: conversation.id,
      direction: 'inbound',
      wamid: msg.messageId,
      type: msg.type === 'audio' ? 'audio' : 'text',
      body: messageText,
      author: 'customer',
      billingCategory: 'service',
      costEstimateMinor: 0,
      rawPayload: { from: msg.from, type: msg.type }
    });

    // 5. Merchant Owner Command Guard
    const ownerCmd = parseOwnerCommand(messageText);
    if (ownerCmd) {
      const tenant = await this.tenantRepo.getById(tenantId);
      if (tenant && this.ownerControlPlane.isOwnerPhone(tenant.config, msg.from)) {
        const cmdResult = await this.ownerControlPlane.executeCommand({
          command: ownerCmd,
          tenantConfig: tenant.config,
          sessionRepo: this.sessionRepo,
          tenantRepo: this.tenantRepo
        });

        await this.whatsappClient.sendTextMessage(msg.from, cmdResult.replyText);
        return;
      }
    }

    // 6. Check Conversation AI Mode (if off / manual takeover, suppress AI)
    if (conversation.aiMode === 'off') {
      return;
    }

    // 7. Get or Create Web/Agent Turn Session
    let session = await this.sessionRepo.getSession(tenantId, `wa_${msg.from}`);
    const sessionId = session?.id || crypto.randomUUID();
    if (!session) {
      session = await this.sessionRepo.createSession({
        id: sessionId,
        tenantId,
        channel: 'whatsapp',
        stage: 'greet',
        externalRef: msg.from
      });
    } else if (session.stage === 'handoff') {
      return;
    }

    // 8. Execute AI Turn
    const turnResult = await this.turnExecutor.executeTurn({
      tenantId,
      sessionId,
      message: {
        id: msg.messageId,
        channel: 'whatsapp',
        sessionId,
        senderId: msg.from,
        content: messageText,
        timestamp: inboundTime.toISOString()
      },
      history: [],
      stage: (session?.stage as 'greet') || 'greet',
      locale: contact.language || 'de'
    });

    const replyText = turnResult.chunks.join('\n\n');
    if (!replyText) return;

    // 9. 24-Hour Service Window Outbound Check
    const now = new Date();
    const isWithinWindow = now.getTime() <= serviceWindowExpiresAt.getTime();

    if (isWithinWindow) {
      // Chunk into natural WhatsApp conversational bubbles
      const { bubbles } = chunkReplyForWhatsApp(replyText);
      for (const bubble of bubbles) {
        const sendResult = await this.whatsappClient.sendTextMessage(msg.from, bubble);
        await this.messageRepo.addMessage({
          tenantId,
          conversationId: conversation.id,
          direction: 'outbound',
          wamid: sendResult.messageId,
          type: 'text',
          body: bubble,
          author: 'agent',
          billingCategory: 'service',
          costEstimateMinor: 0
        });
      }
    } else {
      // Out of 24h window: Freeform text is prohibited by Meta Cloud API policy
      // Fallback to Meta Approved Template Message
      const templateResult = await this.whatsappClient.sendTemplateMessage(
        msg.from,
        this.fallbackTemplateName,
        contact.language || 'de',
        [
          {
            type: 'body',
            parameters: [{ type: 'text', text: contact.displayName || 'Kunde' }]
          }
        ]
      );

      await this.messageRepo.addMessage({
        tenantId,
        conversationId: conversation.id,
        direction: 'outbound',
        wamid: templateResult.messageId,
        type: 'text',
        body: `[Template: ${this.fallbackTemplateName}]`,
        author: 'system',
        billingCategory: 'utility',
        costEstimateMinor: 2
      });
    }
  }
}
