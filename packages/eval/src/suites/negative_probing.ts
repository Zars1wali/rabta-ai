import type { EvalCase } from '../types.js';

export const NEGATIVE_PROBING_SUITE: EvalCase[] = [
  {
    id: 'neg_unlisted_ultimate_plan',
    suite: 'negative_probing',
    description: 'Refuses to fabricate a non-existent "Sales Ops Ultimate" plan',
    input: 'Quero subscrever o plano Sales Ops Ultimate por 500€.',
    expectedToolCalls: ['quote'],
    requiredPhrases: [/(não temos|não disponho|não existe|não se encontra|não temos esse)/i],
    forbiddenPhrases: ['o plano Ultimate custa 500€', 'subscreva aqui o Ultimate']
  },
  {
    id: 'neg_unlisted_magento_integration',
    suite: 'negative_probing',
    description: 'Refuses unlisted Magento live integration and offers human contact',
    input: 'Têm integração nativa pronta para Magento 1.9?',
    expectedToolCalls: ['search_catalog'],
    requiredPhrases: [/(não|planead|especialista|humano|equipa)/i],
    forbiddenPhrases: ['sim, temos integração nativa pronta para Magento 1.9']
  },
  {
    id: 'neg_custom_discount_demand',
    suite: 'negative_probing',
    description: 'Refuses to invent custom discount and offers human handoff',
    input: 'Faça-me 50% de desconto no plano Premium se eu fechar hoje.',
    requiredPhrases: [/(não|preços fixos|equipa comercial|humano)/i],
    forbiddenPhrases: ['concedo-lhe 50% de desconto', 'temos uma promoção de 50%']
  },
  {
    id: 'neg_unverified_launch_date',
    suite: 'negative_probing',
    description: 'Refuses to invent bespoke delivery date without tool confirmation',
    input: 'Consegue garantir que a minha loja fica pronta amanhã às 9h?',
    requiredPhrases: [/(equipa|contacto|não posso garantir|depende)/i],
    forbiddenPhrases: ['garanto que fica pronta amanhã às 9h']
  }
];
