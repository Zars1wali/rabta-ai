import type { ObjectionKind, ObjectionGuidance } from './types.js';

export const OBJECTION_GUIDELINES: Record<ObjectionKind, ObjectionGuidance> = {
  price_expensive: {
    kind: 'price_expensive',
    description: 'Visitor feels the subscription price is too high or questions ROI.',
    recommendedStrategy:
      'Compare fairly against the cost of employing human staff for 24/7 coverage. Emphasize that the agent captures leads and sales outside business hours.',
    forbiddenTactics: [
      'NEVER invent or promise custom discounts without tool authorization.',
      'NEVER manufacture fake promotional deadlines or urgency (e.g. "only valid today").',
      'NEVER promise free trial extensions.'
    ]
  },
  wants_human: {
    kind: 'wants_human',
    description: 'Visitor states their customers prefer talking to real people.',
    recommendedStrategy:
      'Agree with the visitor. Explain that the AI agent handles routine questions and after-hours coverage, with seamless instant human escalation when requested.',
    forbiddenTactics: [
      'NEVER claim the AI is a human.',
      'NEVER disparage the need for human staff.',
      'NEVER refuse to hand off when requested.'
    ]
  },
  indecision_thinking: {
    kind: 'indecision_thinking',
    description: 'Visitor says "I will think about it" or hesitates to commit.',
    recommendedStrategy:
      'Offer a soft diagnostic: ask if there is a specific question or doubt they would like to clarify, or offer the 50 EUR paid preview on their own catalog.',
    forbiddenTactics: [
      'NEVER push, beg, or badger the visitor.',
      'NEVER invent artificial scarcity (e.g. "only 2 onboarding slots left").'
    ]
  },
  privacy_data_gdpr: {
    kind: 'privacy_data_gdpr',
    description: 'Visitor asks about GDPR compliance, data storage, or AI Act obligations.',
    recommendedStrategy:
      'State verified facts: EU AI Act Art. 50 disclosure on first message, 30-day data retention, and EU data residency options.',
    forbiddenTactics: [
      'NEVER provide legal advice.',
      'NEVER invent sub-processors or storage regions not verified by tool policy.'
    ]
  },
  setup_complexity: {
    kind: 'setup_complexity',
    description: 'Visitor worries that connecting their catalog or setup takes too long.',
    recommendedStrategy:
      'Explain that the catalog is synced via standard JSON/CSV feed, WooCommerce, or direct store connector in minutes without code changes.',
    forbiddenTactics: [
      'NEVER promise unrealistic delivery dates or bespoke engineering.'
    ]
  }
};

export function detectObjectionKind(messageText: string): ObjectionKind | null {
  const lower = messageText.toLowerCase();

  if (
    lower.includes('caro') ||
    lower.includes('caríssimo') ||
    lower.includes('desconto') ||
    lower.includes('expensive') ||
    lower.includes('discount') ||
    lower.includes('demasiado')
  ) {
    return 'price_expensive';
  }

  if (
    lower.includes('humano') ||
    lower.includes('pessoa real') ||
    lower.includes('human') ||
    lower.includes('real person') ||
    lower.includes('atendente')
  ) {
    return 'wants_human';
  }

  if (
    lower.includes('vou pensar') ||
    lower.includes('depois vejo') ||
    lower.includes('think about it') ||
    lower.includes('hesitante') ||
    lower.includes('mais tarde')
  ) {
    return 'indecision_thinking';
  }

  if (
    lower.includes('gdpr') ||
    lower.includes('rgpd') ||
    lower.includes('privacidade') ||
    lower.includes('dados') ||
    lower.includes('privacy') ||
    lower.includes('ai act')
  ) {
    return 'privacy_data_gdpr';
  }

  if (
    lower.includes('difícil') ||
    lower.includes('complicado') ||
    lower.includes('setup') ||
    lower.includes('instalar') ||
    lower.includes('complex')
  ) {
    return 'setup_complexity';
  }

  return null;
}
