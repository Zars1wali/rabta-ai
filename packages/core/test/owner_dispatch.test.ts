import { describe, it, expect, vi, beforeEach } from 'vitest';
import { OwnerWhatsAppDispatcher } from '../src/owner/owner_dispatcher.js';
import { SwissCleaningVerticalPack } from '../src/funnel/vertical_packs.js';
import { WhatsAppCloudClient } from '../src/channels/whatsapp_client.js';
import { StripeBillingService } from '../src/billing/service.js';

describe('Milestone 5: 1-Tap Owner WhatsApp In-the-Loop & Stripe Checkout', () => {
  const TENANT_ID = '11111111-1111-4111-8111-111111111111';
  const LEAD_ID = '44444444-4444-4444-8444-444444444444';
  const CONTACT_ID = '33333333-3333-4333-8333-333333333333';
  const OWNER_PHONE = '+41790000000';
  const CUSTOMER_PHONE = '+41791234567';

  let mockClient: WhatsAppCloudClient;
  let dispatcher: OwnerWhatsAppDispatcher;
  let mockLeadRepo: any;
  let mockContactRepo: any;
  let mockConversationRepo: any;
  let mockMessageRepo: any;
  let mockQuoteRepo: any;
  let mockTenantRepo: any;
  let stripeService: StripeBillingService;

  beforeEach(() => {
    mockClient = new WhatsAppCloudClient({ accessToken: 'test_token', phoneNumberId: '123' });
    stripeService = new StripeBillingService();

    mockLeadRepo = {
      listLeadsByTenant: vi.fn().mockResolvedValue([
        {
          id: LEAD_ID,
          tenantId: TENANT_ID,
          contactId: CONTACT_ID,
          conversationId: 'conv_001',
          state: 'qualifying',
          valueEstimateMinor: 118000,
          currency: 'CHF'
        }
      ]),
      updateLeadState: vi.fn().mockResolvedValue({ id: LEAD_ID, state: 'quoted' })
    };

    mockContactRepo = {
      getContactById: vi.fn().mockResolvedValue({
        id: CONTACT_ID,
        displayName: 'Thomas Meier',
        phoneE164: CUSTOMER_PHONE
      })
    };

    mockConversationRepo = {
      updateAiMode: vi.fn().mockResolvedValue({ id: 'conv_001', aiMode: 'off' })
    };

    mockMessageRepo = {
      addMessage: vi.fn().mockResolvedValue({ id: 'msg_001' })
    };

    mockQuoteRepo = {};

    mockTenantRepo = {
      getById: vi.fn().mockResolvedValue({
        id: TENANT_ID,
        displayName: 'Swiss Clean Pro',
        config: { ownerPhone: OWNER_PHONE }
      })
    };

    dispatcher = new OwnerWhatsAppDispatcher({
      whatsappClient: mockClient,
      leadRepo: mockLeadRepo,
      contactRepo: mockContactRepo,
      conversationRepo: mockConversationRepo,
      messageRepo: mockMessageRepo,
      quoteRepo: mockQuoteRepo,
      tenantRepo: mockTenantRepo
    });
  });

  describe('1. 1-Tap Owner WhatsApp Inbound Lead Notification', () => {
    it('sends formatted lead summary with 1-tap slash command instructions to trade owner', async () => {
      const sendSpy = vi.spyOn(mockClient, 'sendTextMessage').mockResolvedValue({ ok: true, messageId: 'out_owner_001' });

      const quoteCalc = SwissCleaningVerticalPack.calculateQuote({
        serviceType: 'move_out_deep_clean',
        rooms: 4.5,
        handoverGuarantee: true
      });

      const sent = await dispatcher.notifyOwnerOfNewQuote({
        tenantId: TENANT_ID,
        leadId: LEAD_ID,
        contactId: CONTACT_ID,
        customerPhone: CUSTOMER_PHONE,
        customerName: 'Thomas Meier',
        quoteCalc,
        location: '8001 Zürich',
        rooms: 4.5,
        targetDate: '15.10.2026'
      });

      expect(sent).toBe(true);
      expect(sendSpy).toHaveBeenCalledWith(
        OWNER_PHONE,
        expect.stringContaining('Neue Offerten-Anfrage (Swiss Clean Pro)')
      );
      expect(sendSpy).toHaveBeenCalledWith(
        OWNER_PHONE,
        expect.stringContaining('/approve 44444444')
      );
    });
  });

  describe('2. Owner Interactive Slash Commands (/approve, /override, /handoff)', () => {
    it('processes /approve command: transitions lead to quoted and dispatches quote & Stripe link to customer', async () => {
      const sendSpy = vi.spyOn(mockClient, 'sendTextMessage').mockResolvedValue({ ok: true, messageId: 'out_cust_001' });

      const replyToOwner = await dispatcher.handleOwnerCommand({
        tenantId: TENANT_ID,
        senderPhone: OWNER_PHONE,
        commandText: '/approve 44444444',
        stripeCheckoutUrlGenerator: async (amountMinor, currency, leadId) => {
          const session = await stripeService.createTradeQuoteCheckoutSession({
            tenantId: TENANT_ID,
            leadId,
            amountMinor,
            currency,
            title: 'Endreinigung 4.5 Zimmer mit Abnahmegarantie'
          });
          return session.checkoutUrl;
        }
      });

      expect(mockLeadRepo.updateLeadState).toHaveBeenCalledWith(TENANT_ID, LEAD_ID, 'quoted');
      expect(sendSpy).toHaveBeenCalledWith(
        CUSTOMER_PHONE,
        expect.stringContaining('CHF 1180.00')
      );
      expect(sendSpy).toHaveBeenCalledWith(
        CUSTOMER_PHONE,
        expect.stringContaining('https://checkout.stripe.com/pay/')
      );
      expect(replyToOwner).toContain('Offerte für Lead #44444444');
    });

    it('processes /override command: updates custom price and sends revised quote to customer', async () => {
      const sendSpy = vi.spyOn(mockClient, 'sendTextMessage').mockResolvedValue({ ok: true });

      const replyToOwner = await dispatcher.handleOwnerCommand({
        tenantId: TENANT_ID,
        senderPhone: OWNER_PHONE,
        commandText: '/override 44444444 1250'
      });

      expect(mockLeadRepo.updateLeadState).toHaveBeenCalledWith(TENANT_ID, LEAD_ID, 'quoted');
      expect(sendSpy).toHaveBeenCalledWith(
        CUSTOMER_PHONE,
        expect.stringContaining('CHF 1250.00')
      );
      expect(replyToOwner).toContain('angepasst und an Kunden gesendet');
    });

    it('processes /handoff command: pauses AI mode and confirms manual takeover to owner', async () => {
      const replyToOwner = await dispatcher.handleOwnerCommand({
        tenantId: TENANT_ID,
        senderPhone: OWNER_PHONE,
        commandText: '/handoff 44444444'
      });

      expect(mockConversationRepo.updateAiMode).toHaveBeenCalledWith('conv_001', 'off', TENANT_ID);
      expect(replyToOwner).toContain('Gespräch für Lead #44444444');
      expect(replyToOwner).toContain('KI-Autopilot ist für diese Konversation pausiert');
    });
  });

  describe('3. Stripe Checkout Session Generation for Trade Quotes', () => {
    it('generates secure Stripe checkout URLs in Swiss Francs (CHF)', async () => {
      const session = await stripeService.createTradeQuoteCheckoutSession({
        tenantId: TENANT_ID,
        leadId: LEAD_ID,
        amountMinor: 118000,
        currency: 'CHF',
        title: 'Endreinigung 4.5 Zimmer'
      });

      expect(session.checkoutUrl).toContain('https://checkout.stripe.com/pay/');
      expect(session.checkoutUrl).toContain('currency=CHF');
      expect(session.checkoutUrl).toContain('amount=118000');
    });
  });
});
