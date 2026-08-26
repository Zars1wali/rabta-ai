import { describe, it, expect } from 'vitest';
import {
  WebChannel,
  WhatsAppChannel,
  chunkReplyForWhatsApp
} from '../src/channels/index.js';

describe('Channels and Message Chunking', () => {
  const sessionId = '550e8400-e29b-41d4-a716-446655440000';

  describe('WebChannel', () => {
    const webChannel = new WebChannel();

    it('identifies as web with no media support', () => {
      expect(webChannel.kind).toBe('web');
      expect(webChannel.supportsMedia).toEqual({ image: false, audio: false });
    });

    it('normalizes inbound web payload', async () => {
      const inbound = await webChannel.normalize({
        sessionId,
        content: 'Olá, gostaria de saber os preços.'
      });

      expect(inbound.channel).toBe('web');
      expect(inbound.sessionId).toBe(sessionId);
      expect(inbound.content).toBe('Olá, gostaria de saber os preços.');
      expect(inbound.senderId).toBe('visitor');
    });

    it('formats single bubble delivery with proportional typing delay', () => {
      const shortText = 'O plano Standard custa 79€/mês.';
      const delivery = webChannel.formatDelivery(sessionId, shortText);

      expect(delivery.channel).toBe('web');
      expect(delivery.sessionId).toBe(sessionId);
      expect(delivery.bubble).toBe(shortText);
      expect(delivery.typingDelayMs).toBeGreaterThanOrEqual(400);
      expect(delivery.typingDelayMs).toBeLessThanOrEqual(2000);
    });
  });

  describe('WhatsAppChannel', () => {
    const waChannel = new WhatsAppChannel();

    it('identifies as whatsapp with image and audio media support', () => {
      expect(waChannel.kind).toBe('whatsapp');
      expect(waChannel.supportsMedia).toEqual({ image: true, audio: true });
    });

    it('normalizes inbound whatsapp payload', async () => {
      const inbound = await waChannel.normalize({
        sessionId,
        phone: '+351912345678',
        text: 'Quero testar o agente na minha loja.'
      });

      expect(inbound.channel).toBe('whatsapp');
      expect(inbound.sessionId).toBe(sessionId);
      expect(inbound.senderId).toBe('+351912345678');
      expect(inbound.content).toBe('Quero testar o agente na minha loja.');
    });
  });

  describe('chunkReplyForWhatsApp Chunker', () => {
    it('keeps short text in a single bubble with 0ms initial delay', () => {
      const text = 'Olá! O plano Lite custa 29€ por mês com 300 conversas incluídas.';
      const result = chunkReplyForWhatsApp(text);

      expect(result.bubbles.length).toBe(1);
      expect(result.bubbles[0]).toBe(text);
      expect(result.delaysMs).toEqual([0]);
    });

    it('splits longer text across clean sentence boundaries', () => {
      const sentence1 = 'O plano Standard custa 79€ por mês e inclui 500 conversas mensais com suporte ao WhatsApp e à Web.';
      const sentence2 = 'Inclui também suporte para notas de voz e imagens de produtos dos clientes.';
      const sentence3 = 'Pode subscrever diretamente pelo link ou solicitar uma demonstração personalizada no seu catálogo por 50€.';
      const fullText = `${sentence1} ${sentence2} ${sentence3}`;

      const result = chunkReplyForWhatsApp(fullText, 140, 1200);

      expect(result.bubbles.length).toBeGreaterThan(1);
      // Each bubble should be <= targetCharCount + tolerance
      for (const bubble of result.bubbles) {
        expect(bubble.length).toBeLessThanOrEqual(140);
      }
      expect(result.delaysMs[0]).toBe(0);
      expect(result.delaysMs[1]).toBe(1200);
    });

    it('splits oversized sentences gracefully without dropping words', () => {
      const longSentence =
        'Este é um texto extremamente longo sem qualquer pontuação final que ultrapassa deliberadamente o limite máximo de caracteres configurado para o teste do chunker de mensagens de WhatsApp para garantir que a divisão por palavras funciona perfeitamente sem quebrar no meio de termos.';

      const result = chunkReplyForWhatsApp(longSentence, 100);

      expect(result.bubbles.length).toBeGreaterThan(1);
      const combined = result.bubbles.join(' ');
      expect(combined.replace(/\s+/g, ' ')).toBe(longSentence.replace(/\s+/g, ' '));
    });

    it('handles empty or whitespace-only input', () => {
      const result = chunkReplyForWhatsApp('   ');
      expect(result.bubbles).toEqual([]);
      expect(result.delaysMs).toEqual([]);
    });
  });
});
