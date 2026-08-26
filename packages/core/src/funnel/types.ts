import type { FunnelStage, AgentEvent } from '@salesops/types';

export interface StageTransitionProposal {
  from: FunnelStage;
  to: FunnelStage;
  reason?: string;
  triggerEvent?: AgentEvent;
}

export interface StageTransitionResult {
  accepted: boolean;
  stage: FunnelStage;
  rejectionReason?: string;
}

export type ObjectionKind =
  | 'price_expensive'
  | 'wants_human'
  | 'indecision_thinking'
  | 'privacy_data_gdpr'
  | 'setup_complexity';

export interface ObjectionGuidance {
  kind: ObjectionKind;
  description: string;
  recommendedStrategy: string;
  forbiddenTactics: string[];
}
