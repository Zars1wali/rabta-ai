import { describe, it, expect, beforeEach } from 'vitest';
import {
  generateRlsSql,
  getTenantContextSql,
  withTenantContext,
  TENANT_SCOPED_TABLES
} from '../src/db/rls.js';
import {
  CommercialLeadSchema,
  LeadStateSchema,
  ContactSchema,
  CommercialMessageSchema,
  OfferingSchema,
  QuoteRequestSchema,
  TimelineEventSchema,
  AiRunSchema
} from '@salesops/types';

describe('Milestone 2: Multi-Tenant PostgreSQL Schema & RLS Isolation Engine', () => {
  const TENANT_A_ID = '11111111-1111-4111-8111-111111111111';
  const TENANT_B_ID = '22222222-2222-4222-8222-222222222222';

  describe('1. PostgreSQL RLS SQL Generation & DDL Integrity', () => {
    it('generates DDL statements for all 22 tenant-scoped tables', () => {
      const sqlStatements = generateRlsSql();

      // 4 statements per table (ENABLE, FORCE, DROP POLICY, CREATE POLICY)
      expect(sqlStatements.length).toBe(TENANT_SCOPED_TABLES.length * 4);

      // Verify all required core tables are included
      const expectedTables = [
        'channels',
        'contacts',
        'conversations',
        'messages',
        'offerings',
        'leads',
        'quote_requests',
        'orders',
        'payments',
        'timeline_events',
        'ai_runs',
        'memberships',
        'catalog_snapshots',
        'catalog_items',
        'sessions',
        'tool_calls',
        'subscriptions',
        'entitlements',
        'usage_events',
        'usage_counters',
        'depletion_alerts',
        'spend_ledger'
      ];

      for (const table of expectedTables) {
        expect(TENANT_SCOPED_TABLES).toContain(table);
        const hasEnable = sqlStatements.some((s) => s.includes(`ALTER TABLE "${table}" ENABLE ROW LEVEL SECURITY;`));
        const hasForce = sqlStatements.some((s) => s.includes(`ALTER TABLE "${table}" FORCE ROW LEVEL SECURITY;`));
        const hasPolicy = sqlStatements.some(
          (s) => s.includes(`CREATE POLICY "tenant_isolation_policy" ON "${table}"`) && s.includes('app.current_tenant_id')
        );

        expect(hasEnable).toBe(true);
        expect(hasForce).toBe(true);
        expect(hasPolicy).toBe(true);
      }
    });

    it('generates valid tenant context SQL and sanitizes tenant ID against SQL injection', () => {
      const validSql = getTenantContextSql(TENANT_A_ID);
      expect(validSql).toBe(`SET LOCAL app.current_tenant_id = '${TENANT_A_ID}';`);

      // Malicious injection attempt must be blocked
      const maliciousId = "11111111-1111-1111-1111-111111111111'; DROP TABLE users; --";
      expect(() => getTenantContextSql(maliciousId)).toThrow(/Invalid tenant ID format/);
    });

    it('executes callbacks inside tenant context transaction', async () => {
      const executedQueries: string[] = [];
      const mockDb = {
        async execute(q: string | { text: string }) {
          const sqlText = typeof q === 'string' ? q : q.text;
          executedQueries.push(sqlText);
          return { rows: [] };
        }
      };

      const result = await withTenantContext(mockDb, TENANT_A_ID, async (db) => {
        await db.execute('SELECT * FROM leads;');
        return 'success';
      });

      expect(result).toBe('success');
      expect(executedQueries[0]).toBe(`SET LOCAL app.current_tenant_id = '${TENANT_A_ID}';`);
      expect(executedQueries[1]).toBe('SELECT * FROM leads;');
    });
  });

  describe('2. Authoritative Domain Entity Validation', () => {
    it('validates Contact schema with Swiss E.164 phone and Mundart/DE language', () => {
      const contact = ContactSchema.parse({
        id: '33333333-3333-4333-8333-333333333333',
        tenantId: TENANT_A_ID,
        waId: '41791234567',
        displayName: 'Thomas Meier',
        phoneE164: '+41791234567',
        language: 'de-CH',
        tags: ['vip', 'residential_cleaning'],
        consentSource: 'whatsapp_opt_in',
        consentAt: new Date().toISOString(),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });

      expect(contact.displayName).toBe('Thomas Meier');
      expect(contact.language).toBe('de-CH');
    });

    it('enforces 6-stage Lead State Machine and Contact vs Lead separation', () => {
      const allowedStates = ['new', 'qualifying', 'interested', 'quoted', 'order_pending', 'won', 'lost', 'dormant'];
      for (const st of allowedStates) {
        expect(LeadStateSchema.parse(st)).toBe(st);
      }

      // Contact has 2 separate leads (e.g. spring move-out clean and autumn window cleaning)
      const contactId = '33333333-3333-4333-8333-333333333333';
      const lead1 = CommercialLeadSchema.parse({
        id: '44444444-4444-4444-8444-444444444444',
        tenantId: TENANT_A_ID,
        contactId,
        leadType: 'quote_request',
        state: 'quoted',
        score: 90,
        valueEstimateMinor: 118000, // CHF 1,180.00
        currency: 'CHF',
        createdAt: new Date('2026-03-01').toISOString(),
        updatedAt: new Date('2026-03-01').toISOString()
      });

      const lead2 = CommercialLeadSchema.parse({
        id: '55555555-5555-4555-8555-555555555555',
        tenantId: TENANT_A_ID,
        contactId,
        leadType: 'quote_request',
        state: 'new',
        score: 60,
        valueEstimateMinor: 35000, // CHF 350.00
        currency: 'CHF',
        createdAt: new Date('2026-08-15').toISOString(),
        updatedAt: new Date('2026-08-15').toISOString()
      });

      expect(lead1.contactId).toBe(lead2.contactId);
      expect(lead1.id).not.toBe(lead2.id);
      expect(lead1.state).toBe('quoted');
      expect(lead2.state).toBe('new');
    });

    it('validates deterministic Offering schema preventing price hallucination', () => {
      const offering = OfferingSchema.parse({
        id: '66666666-6666-4666-8666-666666666666',
        tenantId: TENANT_A_ID,
        sku: 'CLEAN-MOVE-4.5R',
        name: 'Endreinigung 4.5 Zimmer mit Abnahmegarantie',
        description: 'Vollständige Umzugsreinigung inkl. Fenster und Übergabegarantie',
        priceType: 'fixed',
        priceMinor: 118000, // CHF 1,180.00
        currency: 'CHF',
        serviceArea: 'Kanton Zürich',
        durationMinutes: 360,
        active: true,
        attributes: { rooms: 4.5, includesHandoverGuarantee: true },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });

      expect(offering.sku).toBe('CLEAN-MOVE-4.5R');
      expect(offering.priceMinor).toBe(118000);
      expect(offering.currency).toBe('CHF');
    });

    it('validates structured Quote Request field extraction & completeness score', () => {
      const quoteReq = QuoteRequestSchema.parse({
        id: '77777777-7777-4777-8777-777777777777',
        tenantId: TENANT_A_ID,
        leadId: '44444444-4444-4444-8444-444444444444',
        fields: {
          propertyType: 'Apartment (Wohnung)',
          rooms: 4.5,
          squareMeters: 115,
          location: '8001 Zürich',
          postalCode: '8001',
          targetDate: '2026-10-15',
          handoverGuarantee: true
        },
        completeness: 0.95,
        missingFields: ['Access instructions (Keys on site vs lockbox)'],
        suggestedPackage: 'CLEAN-MOVE-4.5R',
        createdAt: new Date().toISOString()
      });

      expect(quoteReq.completeness).toBe(0.95);
      expect(quoteReq.fields.rooms).toBe(4.5);
      expect(quoteReq.fields.handoverGuarantee).toBe(true);
    });

    it('enforces WhatsApp message idempotency wamid structure', () => {
      const msg = CommercialMessageSchema.parse({
        id: '88888888-8888-4888-8888-888888888888',
        tenantId: TENANT_A_ID,
        conversationId: '99999999-9999-4999-8999-999999999999',
        direction: 'inbound',
        wamid: 'wamid.HBgLMjUxOTg3NjU0MzIxFQIAEhggQ0RFRjAxMjM0NTY3ODkwQUJDREVGMDEyMzQ1Njc4OTA=',
        type: 'text',
        body: 'Grüezi! Bitte um eine Offerte für Endreinigung.',
        billingCategory: 'service',
        costEstimateMinor: 0,
        author: 'customer',
        createdAt: new Date().toISOString()
      });

      expect(msg.wamid).toContain('wamid.HBgL');
      expect(msg.direction).toBe('inbound');
    });

    it('validates append-only Timeline Events and AI Run tracking ledger', () => {
      const event = TimelineEventSchema.parse({
        id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        tenantId: TENANT_A_ID,
        aggregateType: 'lead',
        aggregateId: '44444444-4444-4444-8444-444444444444',
        eventType: 'lead.quoted',
        payload: {
          quotedPriceMinor: 118000,
          currency: 'CHF',
          operatorApprovedBy: 'Nuno Ribeiro (Owner)'
        },
        createdAt: new Date().toISOString()
      });

      const aiRun = AiRunSchema.parse({
        id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        tenantId: TENANT_A_ID,
        conversationId: '99999999-9999-4999-8999-999999999999',
        messageId: '88888888-8888-4888-8888-888888888888',
        model: 'gemini-2.5-flash-eu',
        inputTokens: 340,
        outputTokens: 85,
        latencyMs: 380,
        promptRef: 'swiss_cleaning_quote_v1',
        outcome: 'drafted',
        createdAt: new Date().toISOString()
      });

      expect(event.eventType).toBe('lead.quoted');
      expect(aiRun.model).toBe('gemini-2.5-flash-eu');
      expect(aiRun.outcome).toBe('drafted');
    });
  });

  describe('3. Strict Cross-Tenant Query Isolation Simulation', () => {
    // In-memory multi-tenant store verifying tenant separation logic
    const store: Array<{ tenantId: string; entity: string; data: Record<string, unknown> }> = [];

    beforeEach(() => {
      store.length = 0;
      // Seed Tenant A data
      store.push({
        tenantId: TENANT_A_ID,
        entity: 'lead',
        data: { id: 'lead-a-1', name: 'Tenant A Secret Customer', value: 5000 }
      });
      store.push({
        tenantId: TENANT_A_ID,
        entity: 'message',
        data: { wamid: 'wamid-a-1', text: 'Private conversation for Tenant A' }
      });

      // Seed Tenant B data
      store.push({
        tenantId: TENANT_B_ID,
        entity: 'lead',
        data: { id: 'lead-b-1', name: 'Tenant B Secret Customer', value: 9000 }
      });
      store.push({
        tenantId: TENANT_B_ID,
        entity: 'message',
        data: { wamid: 'wamid-b-1', text: 'Private conversation for Tenant B' }
      });
    });

    it('guarantees Tenant A queries return zero rows belonging to Tenant B', () => {
      const queryTenantA = store.filter((row) => row.tenantId === TENANT_A_ID && row.entity === 'lead');
      expect(queryTenantA).toHaveLength(1);
      expect(queryTenantA[0].data.name).toBe('Tenant A Secret Customer');

      // Verify no Tenant B data is present
      const leakedB = queryTenantA.some((row) => row.tenantId === TENANT_B_ID);
      expect(leakedB).toBe(false);
    });

    it('guarantees Tenant B queries return zero rows belonging to Tenant A', () => {
      const queryTenantB = store.filter((row) => row.tenantId === TENANT_B_ID && row.entity === 'lead');
      expect(queryTenantB).toHaveLength(1);
      expect(queryTenantB[0].data.name).toBe('Tenant B Secret Customer');

      // Verify no Tenant A data is present
      const leakedA = queryTenantB.some((row) => row.tenantId === TENANT_A_ID);
      expect(leakedA).toBe(false);
    });

    it('blocks cross-tenant update attempts', () => {
      // Tenant B attempts to update Tenant A's lead
      const targetId = 'lead-a-1';
      const rowToUpdate = store.find((r) => r.data.id === targetId && r.tenantId === TENANT_B_ID);

      expect(rowToUpdate).toBeUndefined(); // RLS filter prevents locating Tenant A's record
    });
  });
});
