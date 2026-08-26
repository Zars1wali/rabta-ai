import type {
  NotificationDispatcher,
  NotificationEvent,
  NotificationDispatchResult
} from './types.js';

export interface OutboundNotificationDispatcherOptions {
  webhookUrl?: string;
  defaultEmailTarget?: string;
  fetchFn?: typeof fetch;
}

export class OutboundNotificationDispatcher implements NotificationDispatcher {
  private webhookUrl?: string;
  private defaultEmailTarget?: string;
  private fetchFn: typeof fetch;

  constructor(options?: OutboundNotificationDispatcherOptions) {
    this.webhookUrl = options?.webhookUrl || process.env.NOTIFY_WEBHOOK_URL;
    this.defaultEmailTarget = options?.defaultEmailTarget || process.env.NOTIFY_EMAIL_TARGET || 'comercial@rewilt.com';
    this.fetchFn = options?.fetchFn || globalThis.fetch;
  }

  async dispatch(event: NotificationEvent): Promise<NotificationDispatchResult> {
    if (this.webhookUrl) {
      try {
        const payload = {
          eventId: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          ...event
        };

        const res = await this.fetchFn(this.webhookUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': 'SalesOps-NotificationDispatcher/1.0'
          },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          return {
            sent: false,
            channel: 'webhook',
            target: this.webhookUrl,
            error: `Webhook server returned status ${res.status}`
          };
        }

        return {
          sent: true,
          channel: 'webhook',
          target: this.webhookUrl
        };
      } catch (err: unknown) {
        return {
          sent: false,
          channel: 'webhook',
          target: this.webhookUrl,
          error: (err as Error).message
        };
      }
    }

    if (event.type === 'handoff_requested' && event.target.type === 'email') {
      const emailTarget = event.target.to || this.defaultEmailTarget || 'comercial@rewilt.com';
      return {
        sent: true,
        channel: 'email',
        target: emailTarget
      };
    }

    return {
      sent: true,
      channel: 'log',
      target: 'system_log'
    };
  }
}

export const defaultNotificationDispatcher = new OutboundNotificationDispatcher();
