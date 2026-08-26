import { z } from 'zod';
import type { Channel, InboundMessage } from '@salesops/types';
import { InboundMessageSchema } from '@salesops/types';
import type { WebDeliveryPayload } from './types.js';

export const WebRawInboundSchema = z.object({
  sessionId: z.string().uuid(),
  content: z.string().min(1, 'Message content cannot be empty'),
  senderId: z.string().optional(),
  mediaUrl: z.string().url().nullable().optional()
});

export class WebChannel implements Channel {
  readonly kind = 'web' as const;
  readonly supportsMedia = { image: false, audio: false };

  async normalize(raw: unknown): Promise<InboundMessage> {
    if (InboundMessageSchema.safeParse(raw).success) {
      return InboundMessageSchema.parse(raw);
    }

    const parsed = WebRawInboundSchema.parse(raw);
    return {
      id: crypto.randomUUID(),
      channel: 'web',
      sessionId: parsed.sessionId,
      senderId: parsed.senderId || 'visitor',
      content: parsed.content,
      mediaUrl: parsed.mediaUrl ?? null,
      timestamp: new Date().toISOString()
    };
  }

  formatDelivery(sessionId: string, text: string): WebDeliveryPayload {
    // Single bubble with typing delay proportional to length (400ms - 2000ms)
    const typingDelayMs = Math.min(2000, Math.max(400, Math.round(text.length * 8)));

    return {
      channel: 'web',
      sessionId,
      bubble: text.trim(),
      typingDelayMs
    };
  }

  async deliver(_sessionId: string, _chunks: string[]): Promise<void> {
    // Handled in SSE stream route in packages/web
    return Promise.resolve();
  }
}
