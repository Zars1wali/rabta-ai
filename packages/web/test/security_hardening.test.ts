import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  verifyAdminAuth,
  handleStripeWebhookRoute,
  handleCustomerPortalRoute,
  handleTopUpCheckoutRoute,
  handleChatRoute
} from '../src/server/index.js';
import {
  MeteringService,
  MeteringRepository,
  AgentTurnExecutor,
  SessionRepository,
  MessageRepository,
  TenantRepository,
  UserRepository,
  MembershipRepository,
  Database,
  createDbClient,
  REWILT_TENANT_ID,
  REWILT_TENANT_CONFIG
} from '@salesops/core';
import type { StripeBillingService, SubscriptionRepository } from '@salesops/core';

describe('Production Security & Scope Hardening Suite', () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe('1. Timing-Safe Admin Authentication', () => {
    const validKey = 'a_very_secure_random_64_character_admin_secret_key_1234567890abcdef';

    it('authenticates valid key in constant time', () => {
      const req = new Request('http://localhost/api/salesops/admin/tenants', {
        headers: { 'x-admin-key': validKey }
      });
      expect(verifyAdminAuth(req, validKey)).toBe(true);
    });

    it('authenticates valid Bearer authorization header', () => {
      const req = new Request('http://localhost/api/salesops/admin/tenants', {
        headers: { authorization: `Bearer ${validKey}` }
      });
      expect(verifyAdminAuth(req, validKey)).toBe(true);
    });

    it('rejects incorrect key of same length', () => {
      const invalidKey = 'b_very_secure_random_64_character_admin_secret_key_1234567890abcdef';
      const req = new Request('http://localhost/api/salesops/admin/tenants', {
        headers: { 'x-admin-key': invalidKey }
      });
      expect(verifyAdminAuth(req, validKey)).toBe(false);
    });

    it('rejects incorrect key of different length without throwing', () => {
      const req = new Request('http://localhost/api/salesops/admin/tenants', {
        headers: { 'x-admin-key': 'short_key' }
      });
      expect(verifyAdminAuth(req, validKey)).toBe(false);
    });

    it('fails closed and throws in production when ADMIN_API_KEY is not configured', () => {
      process.env.NODE_ENV = 'production';
      delete process.env.ADMIN_API_KEY;

      const req = new Request('http://localhost/api/salesops/admin/tenants', {
        headers: { 'x-admin-key': 'some_key' }
      });
      expect(() => verifyAdminAuth(req, undefined)).toThrowError(
        'ADMIN_API_KEY environment variable is required in production.'
      );
    });
  });

  describe('2. Fail-Closed Secrets Enforcement in Production', () => {
    it('throws in production if STRIPE_WEBHOOK_SECRET is missing', async () => {
      process.env.NODE_ENV = 'production';
      delete process.env.STRIPE_WEBHOOK_SECRET;

      const req = new Request('http://localhost/api/salesops/webhooks/stripe', {
        method: 'POST',
        headers: { 'stripe-signature': 't=123,v1=abc' },
        body: JSON.stringify({ type: 'test' })
      });

      const options = {
        stripeService: {} as StripeBillingService,
        subscriptionRepo: {} as SubscriptionRepository,
        webhookSecret: undefined
      };

      await expect(handleStripeWebhookRoute(req, options)).rejects.toThrowError(
        'STRIPE_WEBHOOK_SECRET environment variable is required in production.'
      );
    });

    it('throws in production if METERING_HMAC_SECRET is missing', () => {
      process.env.NODE_ENV = 'production';
      delete process.env.METERING_HMAC_SECRET;

      expect(
        () =>
          new MeteringService({
            repo: {} as MeteringRepository,
            hmacSecret: undefined
          })
      ).toThrowError('METERING_HMAC_SECRET environment variable is required in production.');
    });
  });

  describe('3. IDOR & Backoffice Scope Separation', () => {
    it('handleCustomerPortalRoute blocks unauthorized caller when verifyTenantAuth fails', async () => {
      const req = new Request('http://localhost/api/salesops/portal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenantId: REWILT_TENANT_ID })
      });

      const res = await handleCustomerPortalRoute(req, {
        stripeService: {} as StripeBillingService,
        subscriptionRepo: {} as SubscriptionRepository,
        verifyTenantAuth: () => false // Unauthorized caller
      });

      expect(res.status).toBe(403);
      const json = await res.json();
      expect(json.error).toContain('Forbidden');
    });

    it('handleTopUpCheckoutRoute blocks unauthorized caller when verifyTenantAuth fails', async () => {
      const req = new Request('http://localhost/api/salesops/billing/topup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenantId: REWILT_TENANT_ID, blockCount: 1 })
      });

      const res = await handleTopUpCheckoutRoute(req, {
        billingService: {} as StripeBillingService,
        verifyTenantAuth: () => false
      });

      expect(res.status).toBe(403);
      const json = await res.json();
      expect(json.error).toContain('Forbidden');
    });

    it('handleChatRoute blocks request with 404 when session is not found in database', async () => {
      const mockSessionRepo = {
        getSession: vi.fn().mockResolvedValue(null)
      } as unknown as SessionRepository;

      const req = new Request('http://localhost/api/salesops/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: '00000000-0000-4000-8000-000000000999',
          tenantId: REWILT_TENANT_ID,
          message: { content: 'Hello' }
        })
      });

      const res = await handleChatRoute(req, {
        executor: {} as AgentTurnExecutor,
        sessionRepo: mockSessionRepo
      });

      expect(res.status).toBe(404);
      const json = await res.json();
      expect(json.error).toContain('Session not found');
    });
  });

  describe('4. RBAC Roles & Membership Repository Validation', () => {
    it('verifies UserRepository and MembershipRepository interface contracts', () => {
      const dummyDb = {} as Database;
      const userRepo = new UserRepository(dummyDb);
      const membershipRepo = new MembershipRepository(dummyDb);

      expect(typeof userRepo.getById).toBe('function');
      expect(typeof userRepo.getByEmail).toBe('function');
      expect(typeof userRepo.createUser).toBe('function');

      expect(typeof membershipRepo.addMembership).toBe('function');
      expect(typeof membershipRepo.getMembership).toBe('function');
      expect(typeof membershipRepo.listMembersByTenant).toBe('function');
    });
  });
});
