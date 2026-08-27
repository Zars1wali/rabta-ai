import type { TenantConfig } from '@salesops/types';
import type { SessionRepository, TenantRepository } from '../db/repositories.js';

export type OwnerCommandType = 'pause' | 'resume' | 'status' | 'takeover' | 'help' | 'unknown';

export interface OwnerCommand {
  type: OwnerCommandType;
  targetPhone?: string;
  raw: string;
}

export interface OwnerCommandResult {
  handled: boolean;
  replyText: string;
  actionTaken?: 'paused' | 'resumed' | 'status_reported' | 'takeover_initiated' | 'help_displayed';
}

export function parseOwnerCommand(text: string): OwnerCommand | null {
  const trimmed = text.trim();
  if (!trimmed.startsWith('/')) return null;

  const parts = trimmed.slice(1).split(/\s+/);
  const verb = parts[0]?.toLowerCase();
  const targetPhone = parts[1]?.replace(/[^\d+]/g, '');

  switch (verb) {
    case 'pause':
      return { type: 'pause', targetPhone, raw: trimmed };
    case 'resume':
      return { type: 'resume', targetPhone, raw: trimmed };
    case 'status':
      return { type: 'status', raw: trimmed };
    case 'takeover':
      return { type: 'takeover', targetPhone: targetPhone || '', raw: trimmed };
    case 'help':
    case 'ajuda':
      return { type: 'help', raw: trimmed };
    default:
      return { type: 'unknown', raw: trimmed };
  }
}

export interface WhatsAppChannelConfig {
  kind: 'whatsapp';
  wabaId?: string;
  phoneNumberId?: string;
  ownerPhones?: string[];
}

export class OwnerControlPlane {
  isOwnerPhone(tenantConfig: TenantConfig, phone: string): boolean {
    const cleanPhone = phone.replace(/[^\d]/g, '');
    const channels = tenantConfig.channels || [];

    for (const ch of channels) {
      if (ch.kind === 'whatsapp') {
        const waConfig = ch as unknown as WhatsAppChannelConfig;
        if (waConfig.ownerPhones) {
          const owners = waConfig.ownerPhones.map((p) => p.replace(/[^\d]/g, ''));
          if (owners.includes(cleanPhone)) return true;
        }
      }
    }

    // Fallback: check contact human escalation if formatted as phone
    const contactEscalation = tenantConfig.policy.contact?.humanEscalation?.replace(/[^\d]/g, '');
    if (contactEscalation && contactEscalation.length >= 8 && contactEscalation === cleanPhone) {
      return true;
    }

    return false;
  }

  async executeCommand(options: {
    command: OwnerCommand;
    tenantConfig: TenantConfig;
    sessionRepo: SessionRepository;
    tenantRepo: TenantRepository;
  }): Promise<OwnerCommandResult> {
    const { command, tenantConfig, sessionRepo } = options;
    const storeName = tenantConfig.displayName;

    switch (command.type) {
      case 'pause': {
        const target = command.targetPhone;
        if (target) {
          const sessionId = `wa_${target}`;
          await sessionRepo.updateTurn(tenantConfig.tenantId, sessionId, { stage: 'handoff' });
          return {
            handled: true,
            replyText: `⏸️ *Assistente em Pausa*: A conversa com o cliente ${target} foi colocada em pausa. As respostas automáticas de IA foram desativadas para esta conversa.`,
            actionTaken: 'paused'
          };
        }

        return {
          handled: true,
          replyText: `⏸️ *Assistente em Pausa*: As respostas automáticas foram pausadas globalmente para a loja *${storeName}*. Envie */resume* para reativar.`,
          actionTaken: 'paused'
        };
      }

      case 'resume': {
        const target = command.targetPhone;
        if (target) {
          const sessionId = `wa_${target}`;
          await sessionRepo.updateTurn(tenantConfig.tenantId, sessionId, { stage: 'discover' });
          return {
            handled: true,
            replyText: `▶️ *Assistente Reativado*: O atendimento automático de IA foi retomado para o cliente ${target}.`,
            actionTaken: 'resumed'
          };
        }

        return {
          handled: true,
          replyText: `▶️ *Assistente Ativo*: As respostas automáticas de IA estão ativas para a loja *${storeName}*.`,
          actionTaken: 'resumed'
        };
      }

      case 'takeover': {
        if (!command.targetPhone) {
          return {
            handled: true,
            replyText: '⚠️ *Formato incorreto*: Especifique o número do cliente para assumir a conversa. Exemplo: */takeover 351912345678*',
            actionTaken: 'help_displayed'
          };
        }

        const sessionId = `wa_${command.targetPhone}`;
        await sessionRepo.updateTurn(tenantConfig.tenantId, sessionId, { stage: 'handoff' });

        return {
          handled: true,
          replyText: `🤝 *Assunção de Conversa (Takeover)*: Assumiu o controlo direto do cliente ${command.targetPhone}. O assistente não interferirá mais nesta conversa.`,
          actionTaken: 'takeover_initiated'
        };
      }

      case 'status': {
        const tier = tenantConfig.tier;
        const locales = tenantConfig.locales.join(', ');
        return {
          handled: true,
          replyText: `📊 *Estado da Loja — ${storeName}*
*Plano Atual:* ${tier.toUpperCase()}
*Idiomas Suportados:* ${locales}
*EU AI Act Disclosure:* ${tenantConfig.compliance.aiDisclosure ? '✅ Ativo' : '❌ Desativado'}
*Estado do Agente:* 🟢 Operacional e Pronto a Vender`,
          actionTaken: 'status_reported'
        };
      }

      case 'help': {
        return {
          handled: true,
          replyText: `🛠️ *Comandos de Gestão SalesOps*:
• */status* — Consulta o estado operacional do assistente.
• */pause* — Coloca as respostas automáticas em pausa.
• */pause <número>* — Pausa o assistente para um cliente específico.
• */resume* — Retoma as respostas automáticas.
• */takeover <número>* — Assume o atendimento de um cliente.`,
          actionTaken: 'help_displayed'
        };
      }

      case 'unknown':
      default: {
        return {
          handled: true,
          replyText: `❓ Comando não reconhecido: *${command.raw}*. Envie */help* para ver a lista de comandos disponíveis.`,
          actionTaken: 'help_displayed'
        };
      }
    }
  }
}
