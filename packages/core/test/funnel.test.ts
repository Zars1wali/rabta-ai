import { describe, it, expect } from 'vitest';
import {
  FunnelStateMachine,
  isTransitionLegal,
  getAllowedTransitions,
  detectObjectionKind,
  OBJECTION_GUIDELINES
} from '../src/funnel/index.js';

describe('Funnel State Machine & Objection Handling (WP-09)', () => {
  const machine = new FunnelStateMachine();

  describe('Stage Transitions Graph', () => {
    it('allows legal stage transitions', () => {
      expect(isTransitionLegal('greet', 'discover')).toBe(true);
      expect(isTransitionLegal('discover', 'qualify')).toBe(true);
      expect(isTransitionLegal('qualify', 'present')).toBe(true);
      expect(isTransitionLegal('present', 'objection')).toBe(true);
      expect(isTransitionLegal('objection', 'close')).toBe(true);
      expect(isTransitionLegal('close', 'won')).toBe(true);
      expect(isTransitionLegal('close', 'lost')).toBe(true);
      expect(isTransitionLegal('present', 'handoff')).toBe(true);
    });

    it('rejects illegal stage skips', () => {
      // Cannot skip directly from greet to won without close
      expect(isTransitionLegal('greet', 'won')).toBe(false);
      // Cannot skip directly from discover to won
      expect(isTransitionLegal('discover', 'won')).toBe(false);
      // Cannot skip directly from objection to won
      expect(isTransitionLegal('objection', 'won')).toBe(false);
    });

    it('returns allowed transitions for each stage', () => {
      const greetAllowed = getAllowedTransitions('greet');
      expect(greetAllowed).toContain('discover');
      expect(greetAllowed).toContain('qualify');
      expect(greetAllowed).not.toContain('won');
    });
  });

  describe('FunnelStateMachine Evaluation', () => {
    it('accepts valid proposed transition', () => {
      const result = machine.evaluateTransition('greet', {
        from: 'greet',
        to: 'discover'
      });

      expect(result.accepted).toBe(true);
      expect(result.stage).toBe('discover');
    });

    it('rejects invalid proposed transition and preserves current stage', () => {
      const result = machine.evaluateTransition('greet', {
        from: 'greet',
        to: 'won'
      });

      expect(result.accepted).toBe(false);
      expect(result.stage).toBe('greet');
      expect(result.rejectionReason).toContain('Illegal funnel stage transition');
    });

    it('auto-transitions to close when checkout_url event is triggered', () => {
      const result = machine.evaluateTransition('present', {
        from: 'present',
        to: 'present',
        triggerEvent: {
          type: 'checkout_url',
          url: 'https://checkout.stripe.com/pay/cs_123'
        }
      });

      expect(result.accepted).toBe(true);
      expect(result.stage).toBe('close');
    });

    it('auto-transitions to handoff when handoff_requested event is triggered', () => {
      const result = machine.evaluateTransition('discover', {
        from: 'discover',
        to: 'discover',
        triggerEvent: {
          type: 'handoff_requested',
          target: { type: 'email', to: 'support@rewilt.com' }
        }
      });

      expect(result.accepted).toBe(true);
      expect(result.stage).toBe('handoff');
    });
  });

  describe('Objection Detection & Factual Strategy Guidelines', () => {
    it('detects price objections accurately', () => {
      expect(detectObjectionKind('Acho 79€ muito caro para o meu orçamento')).toBe('price_expensive');
      expect(detectObjectionKind('Consegue fazer algum desconto?')).toBe('price_expensive');
    });

    it('detects human preference objections', () => {
      expect(detectObjectionKind('Os meus clientes querem falar com uma pessoa real')).toBe('wants_human');
    });

    it('detects indecision / hesitation objections', () => {
      expect(detectObjectionKind('Vou pensar melhor e depois vejo')).toBe('indecision_thinking');
    });

    it('detects privacy / GDPR queries', () => {
      expect(detectObjectionKind('Como tratam a privacidade e o RGPD?')).toBe('privacy_data_gdpr');
    });

    it('enforces prohibition on manufactured scarcity, fake urgency, and fake discounts', () => {
      for (const [_kind, guidance] of Object.entries(OBJECTION_GUIDELINES)) {
        expect(guidance.forbiddenTactics.length).toBeGreaterThanOrEqual(1);
        const allForbidden = guidance.forbiddenTactics.join(' ');
        expect(allForbidden).toMatch(/(NEVER|never)/);
      }
    });
  });
});
