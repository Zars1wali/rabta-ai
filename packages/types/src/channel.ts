import { z } from 'zod';

export const ChannelKindSchema = z.enum(['web', 'whatsapp', 'instagram', 'email']);
export type ChannelKind = z.infer<typeof ChannelKindSchema>;

export const InboundMessageSchema = z.object({
  id: z.string().min(1),
  channel: ChannelKindSchema,
  sessionId: z.string().min(1),
  senderId: z.string().min(1),
  content: z.string(),
  mediaUrl: z.string().url().nullable().optional(),
  timestamp: z.string().datetime(),
  localeHint: z.string().nullable().optional()
});
export type InboundMessage = z.infer<typeof InboundMessageSchema>;

export interface Channel {
  readonly kind: ChannelKind;
  readonly supportsMedia: { image: boolean; audio: boolean };
  normalize(raw: unknown): Promise<InboundMessage>;
  deliver(sessionId: string, chunks: string[]): Promise<void>;
}
