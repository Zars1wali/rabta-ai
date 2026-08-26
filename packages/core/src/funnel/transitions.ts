import type { FunnelStage } from '@salesops/types';

export const LEGAL_STAGE_TRANSITIONS: Record<FunnelStage, FunnelStage[]> = {
  greet: ['discover', 'qualify', 'present', 'close', 'handoff'],
  discover: ['qualify', 'present', 'objection', 'close', 'handoff', 'lost'],
  qualify: ['present', 'objection', 'close', 'handoff', 'lost'],
  present: ['objection', 'close', 'handoff', 'lost'],
  objection: ['present', 'close', 'handoff', 'lost'],
  close: ['won', 'objection', 'handoff', 'lost'],
  won: ['greet', 'discover', 'handoff'],
  handoff: ['greet', 'discover', 'handoff'],
  lost: ['greet', 'discover', 'handoff']
};

export function getAllowedTransitions(currentStage: FunnelStage): FunnelStage[] {
  return LEGAL_STAGE_TRANSITIONS[currentStage] || ['greet', 'discover', 'handoff'];
}

export function isTransitionLegal(from: FunnelStage, to: FunnelStage): boolean {
  if (from === to) return true; // Idempotent stay in current stage is always valid
  const allowed = LEGAL_STAGE_TRANSITIONS[from];
  return allowed ? allowed.includes(to) : false;
}
