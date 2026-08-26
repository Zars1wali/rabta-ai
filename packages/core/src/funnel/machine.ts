import type { FunnelStage } from '@salesops/types';
import type { StageTransitionProposal, StageTransitionResult } from './types.js';
import { isTransitionLegal } from './transitions.js';

export class FunnelStateMachine {
  evaluateTransition(
    currentStage: FunnelStage,
    proposal: StageTransitionProposal
  ): StageTransitionResult {
    // 1. Auto-transition triggers from verified tool events
    if (proposal.triggerEvent) {
      if (proposal.triggerEvent.type === 'checkout_url') {
        if (isTransitionLegal(currentStage, 'close')) {
          return { accepted: true, stage: 'close' };
        }
      }
      if (proposal.triggerEvent.type === 'handoff_requested') {
        return { accepted: true, stage: 'handoff' };
      }
      if (proposal.triggerEvent.type === 'lead_captured') {
        if (currentStage === 'greet' || currentStage === 'discover') {
          return { accepted: true, stage: 'qualify' };
        }
      }
    }

    // 2. Validate proposed stage against legal transition graph
    const targetStage = proposal.to;
    if (isTransitionLegal(currentStage, targetStage)) {
      return {
        accepted: true,
        stage: targetStage
      };
    }

    // 3. Reject illegal transition and preserve current stage
    return {
      accepted: false,
      stage: currentStage,
      rejectionReason: `Illegal funnel stage transition from "${currentStage}" to "${targetStage}".`
    };
  }
}

export const defaultFunnelMachine = new FunnelStateMachine();
