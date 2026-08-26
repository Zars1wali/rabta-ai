import { z } from 'zod';
import type { Channel, InboundMessage } from '@salesops/types';
import { InboundMessageSchema } from '@salesops/types';
import { chunkReplyForWhatsApp } from './chunker.js';
import type { WhatsAppDeliveryPayload } from './types.js';

export const WhatsAppRawInboundSchema = z.object({
  sessionId: z.string().uuid(),
  phone: z.string().min(5),
  text: z.string().min(1),
  mediaUrl: z.string().url().nullable().optional()
});

export class WhatsAppChannel implements Channel {
  readonly kind = 'whatsapp' as const;
  readonly supportsMedia = { image: true, audio: true };

  async normalize(raw: unknown): Promise<InboundMessage> {
    if (InboundMessageSchema.safeParse(raw).success) {
      return InboundMessageSchema.parse(raw);
    }

    const parsed = WhatsAppRawInboundSchema.parse(raw);
    return {
      id: crypto.randomUUID(),
      channel: 'whatsapp',
      sessionId: parsed.sessionId,
      senderId: parsed.phone,
      content: parsed.text,
      mediaUrl: parsed.mediaUrl ?? null,
      timestamp: new Date().toISOString()
    };
  }

  formatDelivery(sessionId: string, text: string): WhatsAppDeliveryPayload {
    const { bubbles, delaysMs } = chunkReplyForWhatsApp(text);
    return {
      channel: 'whatsapp',
      sessionId,
      bubbles,
      delaysMs
    };
  }

  async deliver(_sessionId: string, _chunks: string[]): Promise<void> {
    // Delivered via Meta Cloud API webhook outbound client
    return Promise.resolve();
  }
}
