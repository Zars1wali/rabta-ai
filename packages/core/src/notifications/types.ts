import type { Lead, NotifyTarget } from '@salesops/types';

export type NotificationEvent =
  | {
      type: 'lead_captured';
      tenantId: string;
      sessionId: string;
      lead: Lead;
    }
  | {
      type: 'handoff_requested';
      tenantId: string;
      sessionId: string;
      reason: string;
      target?: NotifyTarget;
      transcript?: Array<{ role: string; content: string }>;
    };

export interface NotificationDispatchResult {
  sent: boolean;
  channel: 'webhook' | 'email' | 'log';
  target: string;
  error?: string;
}

export interface NotificationDispatcher {
  dispatch(event: NotificationEvent): Promise<NotificationDispatchResult>;
}
