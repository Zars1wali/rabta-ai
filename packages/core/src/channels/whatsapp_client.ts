import crypto from 'node:crypto';

export interface WhatsAppClientOptions {
  accessToken?: string;
  phoneNumberId?: string;
  graphApiVersion?: string;
  fetchFn?: typeof fetch;
}

export interface InboundWhatsAppMessage {
  messageId: string; // WhatsApp wamid
  from: string; // E.164 phone number, e.g. "41791234567"
  text: string;
  timestamp: string;
  type: 'text' | 'audio' | 'image' | 'document' | 'button_reply' | 'interactive' | 'unknown';
  mediaId?: string;
  mimeType?: string;
  buttonPayload?: string;
}

export interface WhatsAppSendResult {
  ok: boolean;
  messageId?: string;
  error?: string;
}

export interface WhatsAppTemplateComponent {
  type: 'header' | 'body' | 'button';
  sub_type?: 'url' | 'quick_reply';
  index?: number;
  parameters: Array<{
    type: 'text' | 'currency' | 'date_time' | 'image' | 'document' | 'video';
    text?: string;
    image?: { link: string };
    currency?: { fallback_value: string; code: string; amount_1000: number };
  }>;
}

export class WhatsAppCloudClient {
  private accessToken?: string;
  private phoneNumberId?: string;
  private graphApiVersion: string;
  private fetchFn: typeof fetch;

  constructor(options?: WhatsAppClientOptions) {
    this.accessToken = options?.accessToken || process.env.WHATSAPP_ACCESS_TOKEN;
    this.phoneNumberId = options?.phoneNumberId || process.env.WHATSAPP_PHONE_NUMBER_ID;
    this.graphApiVersion = options?.graphApiVersion || 'v21.0';
    this.fetchFn = options?.fetchFn || globalThis.fetch;
  }

  verifyWebhookChallenge(
    hubMode: string | null,
    hubToken: string | null,
    hubChallenge: string | null,
    expectedToken: string
  ): string | null {
    if (hubMode === 'subscribe' && hubToken === expectedToken && hubChallenge) {
      return hubChallenge;
    }
    return null;
  }

  verifyWebhookSignature(
    rawBody: string,
    signatureHeader: string | null,
    appSecret: string
  ): boolean {
    if (!signatureHeader || !appSecret) return false;

    const signature = signatureHeader.replace(/^sha256=/i, '').trim();
    const expected = crypto.createHmac('sha256', appSecret).update(rawBody).digest('hex');

    try {
      return crypto.timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expected, 'hex'));
    } catch {
      return false;
    }
  }

  parseInboundWebhookPayload(payload: unknown): InboundWhatsAppMessage[] {
    const results: InboundWhatsAppMessage[] = [];
    const obj = payload as {
      entry?: Array<{
        changes?: Array<{
          value?: {
            messages?: Array<{
              id: string;
              from: string;
              timestamp?: string;
              type?: string;
              text?: { body?: string };
              audio?: { id: string; mime_type: string };
              voice?: { id: string; mime_type: string };
              image?: { id: string; mime_type: string; caption?: string };
              document?: { id: string; mime_type: string; filename?: string };
              interactive?: {
                type?: string;
                button_reply?: { id: string; title: string };
                list_reply?: { id: string; title: string; description?: string };
              };
            }>;
          };
        }>;
      }>;
    };

    if (!obj?.entry || !Array.isArray(obj.entry)) return results;

    for (const entry of obj.entry) {
      for (const change of entry.changes || []) {
        const value = change.value;
        if (!value || !Array.isArray(value.messages)) continue;

        for (const msg of value.messages) {
          const messageId = msg.id;
          const from = msg.from;
          const timestamp = msg.timestamp
            ? new Date(parseInt(msg.timestamp, 10) * 1000).toISOString()
            : new Date().toISOString();

          if (msg.type === 'text' && msg.text?.body) {
            results.push({
              messageId,
              from,
              text: msg.text.body,
              timestamp,
              type: 'text'
            });
          } else if (msg.type === 'audio' || msg.type === 'voice') {
            const audioData = msg.audio || msg.voice;
            results.push({
              messageId,
              from,
              text: '[Voice Note]',
              timestamp,
              type: 'audio',
              mediaId: audioData?.id,
              mimeType: audioData?.mime_type || 'audio/ogg; codecs=opus'
            });
          } else if (msg.type === 'image' && msg.image) {
            results.push({
              messageId,
              from,
              text: msg.image.caption || '[Image]',
              timestamp,
              type: 'image',
              mediaId: msg.image.id,
              mimeType: msg.image.mime_type
            });
          } else if (msg.type === 'document' && msg.document) {
            results.push({
              messageId,
              from,
              text: msg.document.filename || '[Document]',
              timestamp,
              type: 'document',
              mediaId: msg.document.id,
              mimeType: msg.document.mime_type
            });
          } else if (msg.type === 'interactive') {
            if (msg.interactive?.type === 'button_reply' && msg.interactive.button_reply) {
              results.push({
                messageId,
                from,
                text: msg.interactive.button_reply.title || '',
                buttonPayload: msg.interactive.button_reply.id,
                timestamp,
                type: 'button_reply'
              });
            } else if (msg.interactive?.type === 'list_reply' && msg.interactive.list_reply) {
              results.push({
                messageId,
                from,
                text: msg.interactive.list_reply.title || '',
                buttonPayload: msg.interactive.list_reply.id,
                timestamp,
                type: 'interactive'
              });
            }
          }
        }
      }
    }

    return results;
  }

  async sendTextMessage(
    to: string,
    text: string,
    previewUrl = false
  ): Promise<WhatsAppSendResult> {
    if (!this.accessToken || !this.phoneNumberId) {
      return { ok: false, error: 'WhatsApp credentials (accessToken / phoneNumberId) not configured.' };
    }

    const url = `https://graph.facebook.com/${this.graphApiVersion}/${this.phoneNumberId}/messages`;
    const payload = {
      messaging_product: 'whatsapp',
      recipient_type: 'individual',
      to,
      type: 'text',
      text: {
        preview_url: previewUrl,
        body: text
      }
    };

    try {
      const res = await this.fetchFn(url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        return {
          ok: false,
          error: `Meta Graph API error: ${res.status} ${JSON.stringify(errJson)}`
        };
      }

      const data = (await res.json()) as { messages?: Array<{ id?: string }> };
      const messageId = data?.messages?.[0]?.id;
      return { ok: true, messageId };
    } catch (err: unknown) {
      return { ok: false, error: (err as Error).message };
    }
  }

  async sendTemplateMessage(
    to: string,
    templateName: string,
    languageCode = 'de',
    components?: WhatsAppTemplateComponent[]
  ): Promise<WhatsAppSendResult> {
    if (!this.accessToken || !this.phoneNumberId) {
      return { ok: false, error: 'WhatsApp credentials (accessToken / phoneNumberId) not configured.' };
    }

    const url = `https://graph.facebook.com/${this.graphApiVersion}/${this.phoneNumberId}/messages`;
    const payload = {
      messaging_product: 'whatsapp',
      recipient_type: 'individual',
      to,
      type: 'template',
      template: {
        name: templateName,
        language: {
          code: languageCode
        },
        components: components || []
      }
    };

    try {
      const res = await this.fetchFn(url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        return {
          ok: false,
          error: `Meta Graph API error: ${res.status} ${JSON.stringify(errJson)}`
        };
      }

      const data = (await res.json()) as { messages?: Array<{ id?: string }> };
      return { ok: true, messageId: data?.messages?.[0]?.id };
    } catch (err: unknown) {
      return { ok: false, error: (err as Error).message };
    }
  }

  async sendInteractiveButtons(
    to: string,
    bodyText: string,
    buttons: Array<{ id: string; title: string }>
  ): Promise<WhatsAppSendResult> {
    if (!this.accessToken || !this.phoneNumberId) {
      return { ok: false, error: 'WhatsApp credentials not configured.' };
    }

    const url = `https://graph.facebook.com/${this.graphApiVersion}/${this.phoneNumberId}/messages`;
    const payload = {
      messaging_product: 'whatsapp',
      recipient_type: 'individual',
      to,
      type: 'interactive',
      interactive: {
        type: 'button',
        body: { text: bodyText },
        action: {
          buttons: buttons.slice(0, 3).map((btn) => ({
            type: 'reply',
            reply: {
              id: btn.id,
              title: btn.title.slice(0, 20)
            }
          }))
        }
      }
    };

    try {
      const res = await this.fetchFn(url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        return {
          ok: false,
          error: `Meta Graph API error: ${res.status} ${JSON.stringify(errJson)}`
        };
      }

      const data = (await res.json()) as { messages?: Array<{ id?: string }> };
      return { ok: true, messageId: data?.messages?.[0]?.id };
    } catch (err: unknown) {
      return { ok: false, error: (err as Error).message };
    }
  }

  async getMediaUrl(mediaId: string): Promise<string | null> {
    if (!this.accessToken) return null;
    const url = `https://graph.facebook.com/${this.graphApiVersion}/${mediaId}`;
    try {
      const res = await this.fetchFn(url, {
        headers: { Authorization: `Bearer ${this.accessToken}` }
      });
      if (!res.ok) return null;
      const data = (await res.json()) as { url?: string };
      return data?.url ?? null;
    } catch {
      return null;
    }
  }

  async downloadMedia(mediaId: string): Promise<{ buffer: Buffer; mimeType?: string } | null> {
    const downloadUrl = await this.getMediaUrl(mediaId);
    if (!downloadUrl || !this.accessToken) return null;

    try {
      const res = await this.fetchFn(downloadUrl, {
        headers: { Authorization: `Bearer ${this.accessToken}` }
      });
      if (!res.ok) return null;
      const arrayBuffer = await res.arrayBuffer();
      const mimeType = res.headers.get('content-type') || undefined;
      return { buffer: Buffer.from(arrayBuffer), mimeType };
    } catch {
      return null;
    }
  }
}
