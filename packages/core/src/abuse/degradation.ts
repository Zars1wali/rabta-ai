import type { DegradedResponseOptions } from './types.js';

export function buildDegradedMessage(options: DegradedResponseOptions): string {
  const isPt = (options.locale || 'pt-PT').startsWith('pt');
  const isEs = (options.locale || 'es-ES').startsWith('es');
  const contact = options.escalationContact || 'comercial@rewilt.com';

  const faqItems = options.storePolicy?.custom?.slice(0, 2) || [];

  if (isPt) {
    let msg = `O limite de mensagens automatizadas desta sessão foi atingido. Para esclarecer dúvidas específicas ou avançar com a subscrição, por favor contacte a nossa equipa através de ${contact}.\n\nPerguntas Frequentes:`;
    if (faqItems.length > 0) {
      for (const faq of faqItems) {
        msg += `\n- ${faq.question}: ${faq.answer}`;
      }
    } else {
      msg += `\n- Planos: Dispomos de planos Standard (79€/mês) e demonstrações no seu catálogo por 50€.`;
    }
    return msg;
  }

  if (isEs) {
    let msg = `Se ha alcanzado el límite de mensajes automáticos de esta sesión. Para resolver dudas específicas o suscribirte, ponte en contacto con nuestro equipo en ${contact}.\n\nPreguntas Frecuentes:`;
    if (faqItems.length > 0) {
      for (const faq of faqItems) {
        msg += `\n- ${faq.question}: ${faq.answer}`;
      }
    } else {
      msg += `\n- Planes: Disponemos de planes Standard (79€/mes) y demostraciones en tu catálogo por 50€.`;
    }
    return msg;
  }

  let msg = `The automated message limit for this session has been reached. To answer specific questions or subscribe, please contact our team at ${contact}.\n\nFrequently Asked Questions:`;
  if (faqItems.length > 0) {
    for (const faq of faqItems) {
      msg += `\n- ${faq.question}: ${faq.answer}`;
    }
  } else {
    msg += `\n- Plans: We offer Standard plans (€79/mo) and custom previews on your catalog for €50.`;
  }
  return msg;
}
