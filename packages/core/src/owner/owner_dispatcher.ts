import type { WhatsAppCloudClient } from '../channels/whatsapp_client.js';
import type {
  CommercialLeadRepository,
  ContactRepository,
  ConversationRepository,
  CommercialMessageRepository,
  QuoteRequestRepository,
  TenantRepository
} from '../db/repositories.js';
import type { GroundedQuoteCalculation } from '../funnel/vertical_packs.js';

export interface OwnerDispatchOptions {
  whatsappClient: WhatsAppCloudClient;
  leadRepo: CommercialLeadRepository;
  contactRepo: ContactRepository;
  conversationRepo: ConversationRepository;
  messageRepo: CommercialMessageRepository;
  quoteRepo: QuoteRequestRepository;
  tenantRepo: TenantRepository;
}

export class OwnerWhatsAppDispatcher {
  constructor(private options: OwnerDispatchOptions) {}

  /**
   * Dispatches a 1-tap actionable notification to the business owner on WhatsApp.
   */
  async notifyOwnerOfNewQuote(params: {
    tenantId: string;
    leadId: string;
    contactId: string;
    customerPhone: string;
    customerName?: string;
    quoteCalc: GroundedQuoteCalculation;
    location?: string;
    rooms?: number;
    targetDate?: string;
  }): Promise<boolean> {
    const tenant = await this.options.tenantRepo.getById(params.tenantId);
    const config = tenant?.config as Record<string, unknown> | undefined;
    const ownerPhone = (config?.ownerPhone as string) || (config?.escalationPhone as string);

    if (!ownerPhone) {
      return false;
    }

    const priceFormatted = (params.quoteCalc.totalPriceMinor / 100).toFixed(2);
    const leadShortId = params.leadId.slice(0, 8);

    const message = [
      `🔔 *Neue Offerten-Anfrage (${tenant?.displayName || 'Nuncio'})*`,
      `Kunde: ${params.customerName || 'Interessent'} (${params.customerPhone})`,
      `• Objekt: ${params.rooms ? `${params.rooms} Zimmer` : 'Wohnung'} ${params.location ? `in ${params.location}` : ''}`,
      `• Datum: ${params.targetDate || 'Nach Vereinbarung'}`,
      `• Garantie: ${params.quoteCalc.includesHandoverGuarantee ? 'Abnahmegarantie inkl.' : 'Standard'}`,
      `• Berechneter Richtpreis: *${params.quoteCalc.currency} ${priceFormatted}* (${params.quoteCalc.sku})`,
      '',
      `Antworte direkt mit:`,
      `*/approve ${leadShortId}* - Offerte direkt freigeben & senden`,
      `*/override ${leadShortId} <preis>* - Preis anpassen (z.B. /override ${leadShortId} 1250)`,
      `*/handoff ${leadShortId}* - Gespräch selbst übernehmen`
    ].join('\n');

    const result = await this.options.whatsappClient.sendTextMessage(ownerPhone, message);
    return result.ok;
  }

  /**
   * Handles an owner command sent via WhatsApp.
   */
  async handleOwnerCommand(params: {
    tenantId: string;
    senderPhone: string;
    commandText: string;
    stripeCheckoutUrlGenerator?: (amountMinor: number, currency: string, leadId: string) => Promise<string>;
  }): Promise<string> {
    const text = params.commandText.trim();
    const parts = text.split(/\s+/);
    const cmd = parts[0]?.toLowerCase();
    const leadShortId = parts[1];

    if (!cmd || !cmd.startsWith('/')) {
      return 'Unbekannter Befehl. Verfügbar: /approve, /override, /handoff, /stats';
    }

    if (cmd === '/stats') {
      const leads = await this.options.leadRepo.listLeadsByTenant(params.tenantId);
      const won = leads.filter((l) => l.state === 'won').length;
      const quoted = leads.filter((l) => l.state === 'quoted').length;
      const newLeads = leads.filter((l) => l.state === 'new').length;
      return `📊 *Lead-Übersicht:*\n• Neu / Offen: ${newLeads}\n• Offertiert: ${quoted}\n• Gewonnen: ${won}\n• Total Leads: ${leads.length}`;
    }

    if (!leadShortId) {
      return 'Bitte geben Sie die Lead-ID an, z.B. `/approve 44444444`';
    }

    // Find lead by short ID prefix
    const allLeads = await this.options.leadRepo.listLeadsByTenant(params.tenantId);
    const targetLead = allLeads.find((l) => l.id.startsWith(leadShortId));

    if (!targetLead) {
      return `Fehler: Lead mit ID-Präfix "${leadShortId}" wurde nicht gefunden.`;
    }

    if (!targetLead.contactId) {
      return `Fehler: Kein Kontakt für Lead ${leadShortId} hinterlegt.`;
    }

    const contact = await this.options.contactRepo.getContactById(params.tenantId, targetLead.contactId);
    if (!contact?.phoneE164) {
      return `Fehler: Kundendaten für Lead ${leadShortId} nicht verfügbar.`;
    }

    if (cmd === '/approve') {
      // 1. Update Lead State
      await this.options.leadRepo.updateLeadState(params.tenantId, targetLead.id, 'quoted');

      const priceFormatted = (targetLead.valueEstimateMinor / 100).toFixed(2);
      let checkoutLinkText = '';

      if (params.stripeCheckoutUrlGenerator && targetLead.valueEstimateMinor > 0) {
        try {
          const checkoutUrl = await params.stripeCheckoutUrlGenerator(
            targetLead.valueEstimateMinor,
            targetLead.currency,
            targetLead.id
          );
          checkoutLinkText = `\n\nDirekt online bestätigen & reservieren:\n${checkoutUrl}`;
        } catch {
          // proceed without link if generator fails
        }
      }

      // 2. Dispatch Official Quote Message to Customer
      const customerMsg = [
        `Guten Tag ${contact.displayName || ''}!`,
        `Hier ist Ihre unverbindliche Offerte für die Endreinigung mit Abnahmegarantie:`,
        `*Total: ${targetLead.currency} ${priceFormatted}* (inkl. Übergabegarantie & Anfahrt).${checkoutLinkText}`,
        '',
        `Passen Ihnen Datum und Preis? Antworten Sie einfach mit "Ja" zur Buchung.`
      ].join('\n');

      await this.options.whatsappClient.sendTextMessage(contact.phoneE164, customerMsg);

      return `✅ Offerte für Lead #${leadShortId} (*${targetLead.currency} ${priceFormatted}*) wurde freigegeben und an ${contact.phoneE164} gesendet.`;
    }

    if (cmd === '/override') {
      const newPriceStr = parts[2];
      const newPrice = parseFloat(newPriceStr || '');
      if (isNaN(newPrice) || newPrice <= 0) {
        return `Bitte geben Sie einen gültigen Betrag an, z.B. \`/override ${leadShortId} 1250\``;
      }

      const newPriceMinor = Math.round(newPrice * 100);
      await this.options.leadRepo.updateLeadState(params.tenantId, targetLead.id, 'quoted');

      const priceFormatted = (newPriceMinor / 100).toFixed(2);
      const customerMsg = [
        `Guten Tag ${contact.displayName || ''}!`,
        `Nach individueller Prüfung bieten wir Ihnen folgenden Festpreis:`,
        `*Total: ${targetLead.currency} ${priceFormatted}* (inkl. Übergabegarantie & aller Nebenkosten).`,
        '',
        `Möchten Sie diesen Termin verbindlich reservieren? Antworten Sie mit "Ja".`
      ].join('\n');

      await this.options.whatsappClient.sendTextMessage(contact.phoneE164, customerMsg);

      return `✅ Preis für Lead #${leadShortId} auf *${targetLead.currency} ${priceFormatted}* angepasst und an Kunden gesendet.`;
    }

    if (cmd === '/handoff') {
      if (targetLead.conversationId) {
        await this.options.conversationRepo.updateAiMode(targetLead.conversationId, 'off', params.tenantId);
      }
      return `🤝 Gespräch für Lead #${leadShortId} (${contact.phoneE164}) übernommen. KI-Autopilot ist für diese Konversation pausiert.`;
    }

    return 'Unbekannter Befehl.';
  }
}
