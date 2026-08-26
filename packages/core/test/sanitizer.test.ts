import { describe, it, expect } from 'vitest';
import { sanitizeReply, limitEmojis } from '../src/agent/sanitizer.js';

describe('Agent Output Sanitizer', () => {
  it('strips markdown headers, bold, italics, and code blocks', () => {
    const raw = `
# Planos Disponíveis
Temos o plano **Sales Ops Standard** por apenas _79€_ por mês!
Use o código \`PROMO10\` para mais detalhes.
`;
    const clean = sanitizeReply(raw);

    expect(clean).not.toContain('#');
    expect(clean).not.toContain('**');
    expect(clean).not.toContain('_');
    expect(clean).not.toContain('`');
    expect(clean).toContain('Temos o plano Sales Ops Standard por apenas 79€ por mês!');
    expect(clean).toContain('Use o código PROMO10 para mais detalhes.');
  });

  it('strips bullet points and numbered lists', () => {
    const raw = `
Aqui estão os benefícios:
- Atendimento 24/7
- Respostas rápidas
* Sem alucinações
1. Primeiro passo
2. Segundo passo
`;
    const clean = sanitizeReply(raw);

    expect(clean).not.toMatch(/^[-*+]\s+/m);
    expect(clean).not.toMatch(/^\d+\.\s+/m);
    expect(clean).toContain('Atendimento 24/7');
    expect(clean).toContain('Respostas rápidas');
    expect(clean).toContain('Sem alucinações');
  });

  it('limits emojis to at most 1 in the reply and strips the rest', () => {
    const multiEmoji = 'Olá! 👋 Seja bem-vindo à loja! 🎉 Temos ótimas ofertas hoje! 🚀✨';
    const singleEmoji = limitEmojis(multiEmoji, 1);

    expect(singleEmoji).toContain('👋');
    expect(singleEmoji).not.toContain('🎉');
    expect(singleEmoji).not.toContain('🚀');
    expect(singleEmoji).not.toContain('✨');
  });

  it('preserves clean text without modification', () => {
    const cleanText = 'O plano Standard inclui 500 conversas por mês e suporte a WhatsApp.';
    expect(sanitizeReply(cleanText)).toBe(cleanText);
  });
});
