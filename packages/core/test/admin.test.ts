import { describe, it, expect, vi } from 'vitest';
import { TenantAdminService } from '../src/admin/index.js';
import type { TenantRepository } from '../src/db/repositories.js';
import { REWILT_TENANT_ID, REWILT_TENANT_CONFIG } from '../src/db/seed.js';
import type { TenantConfig } from '@salesops/types';

describe('TenantConfig Admin Service & Versioning (WP-14)', () => {
  const tenantId = REWILT_TENANT_ID;

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

  it('fetches existing tenant configuration', async () => {
    const res = await adminService.getTenant(tenantId);
    expect(res.ok).toBe(true);
    expect(res.tenant?.slug).toBe('rewilt');
    expect(res.tenant?.config.version).toBe(1);
  });

  it('rejects tenant creation with malformed config schema', async () => {
    const invalidConfig = {
      version: 1,
      // Missing identity, policy, catalogSource, persona!
      displayName: 'Incomplete'
    } as unknown as TenantConfig;

    const res = await adminService.createTenant({
      slug: 'incomplete-shop',
      displayName: 'Incomplete Shop',
      config: invalidConfig
    });

    expect(res.ok).toBe(false);
    expect(res.error).toContain('Invalid TenantConfig schema');
    expect(res.issues).toBeDefined();
  });

  it('updates tenant configuration and increments version from 1 to 2', async () => {
    const updatedConfig: TenantConfig = {
      ...currentConfig,
      persona: {
        ...currentConfig.persona,
        greeting: 'Olá! Sou o consultor sénior da Rewilt.'
      }
    };

    const res = await adminService.updateTenantConfig({
      tenantId,
      config: updatedConfig,
      expectedVersion: 1
    });

    expect(res.ok).toBe(true);
    expect(res.tenant?.config.version).toBe(2);
    expect(res.tenant?.config.persona.greeting).toBe('Olá! Sou o consultor sénior da Rewilt.');
  });

  it('rejects update with 409 Conflict when expectedVersion does not match current version', async () => {
    const updatedConfig: TenantConfig = {
      ...currentConfig,
      persona: {
        ...currentConfig.persona,
        greeting: 'Olá!'
      }
    };

    // Expected version 1, but current version is already 2!
    const res = await adminService.updateTenantConfig({
      tenantId,
      config: updatedConfig,
      expectedVersion: 1
    });

    expect(res.ok).toBe(false);
    expect(res.error).toContain('Conflict');
  });
});
