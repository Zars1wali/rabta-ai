import { describe, it, expect, vi } from 'vitest';
import {
  handleAdminTenantGetRoute,
  handleAdminTenantCreateRoute,
  handleAdminTenantUpdateRoute
} from '../src/server/index.js';
import { TenantAdminService, REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '@salesops/core';
import type { TenantRepository } from '@salesops/core';
import type { TenantConfig } from '@salesops/types';

describe('Admin API Routes & Multi-Tenant Versioning (WP-14)', () => {
  const tenantId = REWILT_TENANT_ID;
  const adminApiKey = 'test_secret_admin_key_999';

  let currentConfig: TenantConfig = {
    ...REWILT_TENANT_CONFIG,
    version: 1
  };

  const mockTenantRepo = {
    getById: vi.fn().mockImplementation(async (id: string) => {
      if (id === tenantId) {
        return {
          id: tenantId,
          slug: 'rewilt',
          displayName: 'Rewilt Sales Ops',
          config: currentConfig,
          createdAt: new Date(),
          updatedAt: new Date()
        };
      }
      return null;
    }),
    getBySlug: vi.fn().mockImplementation(async (slug: string) => {
      if (slug === 'rewilt') {
        return {
          id: tenantId,
          slug: 'rewilt',
          displayName: 'Rewilt Sales Ops',
          config: currentConfig,
          createdAt: new Date(),
          updatedAt: new Date()
        };
      }
      return null;
    }),
    upsert: vi.fn().mockImplementation(async (data) => {
      currentConfig = data.config;
      return {
        id: data.id || tenantId,
        slug: data.slug,
        displayName: data.displayName,
        config: data.config,
        createdAt: new Date(),
        updatedAt: new Date()
      };
    })
  } as unknown as TenantRepository;

  const adminService = new TenantAdminService(mockTenantRepo);

  it('returns 401 Unauthorized if x-admin-key header is missing or incorrect', async () => {
    const req = new Request(`http://localhost/api/salesops/admin/tenants/${tenantId}`, {
      method: 'GET',
      headers: { 'x-admin-key': 'wrong_key' }
    });

    const res = await handleAdminTenantGetRoute(req, { adminService, adminApiKey }, tenantId);
    expect(res.status).toBe(401);
  });

  it('returns 200 OK with tenant details when authenticated with valid admin key', async () => {
    const req = new Request(`http://localhost/api/salesops/admin/tenants/${tenantId}`, {
      method: 'GET',
      headers: { 'x-admin-key': adminApiKey }
    });

    const res = await handleAdminTenantGetRoute(req, { adminService, adminApiKey }, tenantId);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.slug).toBe('rewilt');
  });

  it('updates configuration via PUT route and increments version', async () => {
    const updatedConfig: TenantConfig = {
      ...currentConfig,
      persona: {
        ...currentConfig.persona,
        greeting: 'Olá! Sou o agente especialista da Rewilt.'
      }
    };

    const req = new Request(`http://localhost/api/salesops/admin/tenants/${tenantId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'x-admin-key': adminApiKey
      },
      body: JSON.stringify({
        config: updatedConfig,
        expectedVersion: 1
      })
    });

    const res = await handleAdminTenantUpdateRoute(req, { adminService, adminApiKey }, tenantId);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.config.version).toBe(2);
    expect(data.config.persona.greeting).toBe('Olá! Sou o agente especialista da Rewilt.');
  });

  it('rejects PUT update with 409 Conflict when expectedVersion mismatch occurs', async () => {
    const updatedConfig: TenantConfig = {
      ...currentConfig,
      persona: {
        ...currentConfig.persona,
        greeting: 'Olá!'
      }
    };

    const req = new Request(`http://localhost/api/salesops/admin/tenants/${tenantId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'x-admin-key': adminApiKey
      },
      body: JSON.stringify({
        config: updatedConfig,
        expectedVersion: 1 // Current is already 2!
      })
    });

    const res = await handleAdminTenantUpdateRoute(req, { adminService, adminApiKey }, tenantId);
    expect(res.status).toBe(409);
  });

  it('creates new tenant via POST route when authenticated', async () => {
    const newConfig: TenantConfig = {
      ...currentConfig,
      tenantId: '00000000-0000-4000-8000-000000000002',
      displayName: 'New Merchant'
    };

    const req = new Request('http://localhost/api/salesops/admin/tenants', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-admin-key': adminApiKey
      },
      body: JSON.stringify({
        slug: 'new-merchant',
        displayName: 'New Merchant',
        config: newConfig
      })
    });

    const res = await handleAdminTenantCreateRoute(req, { adminService, adminApiKey });
    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.slug).toBe('new-merchant');
  });
});
