import type { AgentEvent, FunnelStage } from '@salesops/types';

export interface ChatMessage {
  id: string;
  role: 'visitor' | 'agent' | 'system';
  content: string;
  mediaUrl?: string | null;
  createdAt?: string;
  isStreaming?: boolean;
}

export interface WidgetConfig {
  tenantId?: string;
  apiBaseUrl?: string;
  locale?: string;
  storeName?: string;
  primaryColor?: string;
  position?: 'bottom-right' | 'bottom-left';
  initialOpen?: boolean;
  onEvent?: (event: AgentEvent) => void;
  onStageChange?: (stage: FunnelStage) => void;
}

export type ChatStatus = 'idle' | 'loading' | 'streaming' | 'error';
