import type { EvalCase } from '../types.js';

export const PRICE_INTEGRITY_SUITE: EvalCase[] = [
  {
    id: 'price_lite_monthly',
    suite: 'price_integrity',
    description: 'Quotes Sales Ops Lite at exactly 29€/month',
    input: 'Quanto custa o plano Lite?',
    expectedToolCalls: ['quote'],
    requiredPhrases: ['29', 'Lite'],
    forbiddenPhrases: ['19€', '49€', '79€', 'grátis', 'desconto']
  },
  {
    id: 'price_standard_monthly',
    suite: 'price_integrity',
    description: 'Quotes Sales Ops Standard at exactly 79€/month',
    input: 'Qual é o preço do plano Standard?',
    expectedToolCalls: ['quote'],
    requiredPhrases: ['79', 'Standard'],
    forbiddenPhrases: ['59€', '99€', 'desconto de 20%']
  },
  {
    id: 'price_europe_monthly',
    suite: 'price_integrity',
    description: 'Quotes Sales Ops Europe at exactly 99€/month',
    input: 'Quanto custa o plano com residência de dados na Europa?',
    expectedToolCalls: ['quote'],
    requiredPhrases: ['99', 'Europe'],
    forbiddenPhrases: ['79€', '129€']
  },
  {
    id: 'price_premium_monthly',
    suite: 'price_integrity',
    description: 'Quotes Sales Ops Premium at exactly 199€/month',
    input: 'Qual é o valor do plano Premium com suporte prioritário?',
    expectedToolCalls: ['quote'],
    requiredPhrases: ['199', 'Premium'],
    forbiddenPhrases: ['149€', '249€']
  },
  {
    id: 'price_preview_once',
    suite: 'price_integrity',
    description: 'Quotes custom catalog demonstration at exactly 50€ credited on conversion',
    input: 'Posso testar no meu catálogo antes de subscrever? Quanto custa?',
    expectedToolCalls: ['quote'],
    requiredPhrases: ['50', 'creditad'],
    forbiddenPhrases: ['teste grátis sem custos', '100€']
  }
];
