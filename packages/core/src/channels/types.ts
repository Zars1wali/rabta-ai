import type { Channel, InboundMessage } from '@salesops/types';

export interface WebDeliveryPayload {
  channel: 'web';
  sessionId: string;
  bubble: string;
  typingDelayMs: number;
}

export interface WhatsAppDeliveryPayload {
  channel: 'whatsapp';
  sessionId: string;
  bubbles: string[];
  delaysMs: number[];
}

export type { Channel, InboundMessage };
