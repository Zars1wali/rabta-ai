import { TenantConfigSchema, type TenantConfig } from '@salesops/types';
import type {
  CreateTenantOptions,
  TenantAdminResult,
  UpdateTenantConfigOptions
} from './types.js';
import type { TenantRepository } from '../db/repositories.js';

export class TenantAdminService {
  constructor(private tenantRepo: TenantRepository) {}

  async getTenant(tenantId: string): Promise<TenantAdminResult> {
    const row = await this.tenantRepo.getById(tenantId);
    if (!row) {
      return { ok: false, error: `Tenant "${tenantId}" not found.` };
    }

    return {
      ok: true,
      tenant: {
        id: row.id,
        slug: row.slug,
        displayName: row.displayName,
        config: row.config,
        createdAt: row.createdAt.toISOString(),
        updatedAt: row.updatedAt.toISOString()
      }
    };
  }

  async getTenantBySlug(slug: string): Promise<TenantAdminResult> {
    const row = await this.tenantRepo.getBySlug(slug);
    if (!row) {
      return { ok: false, error: `Tenant with slug "${slug}" not found.` };
    }

    return {
      ok: true,
      tenant: {
        id: row.id,
        slug: row.slug,
        displayName: row.displayName,
        config: row.config,
        createdAt: row.createdAt.toISOString(),
        updatedAt: row.updatedAt.toISOString()
      }
    };
  }

  async createTenant(options: CreateTenantOptions): Promise<TenantAdminResult> {
    // 1. Strict Schema Validation
    const validation = TenantConfigSchema.safeParse(options.config);
    if (!validation.success) {
      return {
        ok: false,
        error: 'Invalid TenantConfig schema.',
        issues: validation.error.issues
      };
    }

    const validatedConfig = validation.data;

    // 2. Check slug uniqueness
    const existing = await this.tenantRepo.getBySlug(options.slug);
    if (existing) {
      return {
        ok: false,
        error: `Tenant slug "${options.slug}" already exists.`
      };
    }

    // 3. Persist tenant
    const row = await this.tenantRepo.upsert({
      id: options.id,
      slug: options.slug,
      displayName: options.displayName,
      config: validatedConfig
    });

    return {
      ok: true,
      tenant: {
        id: row.id,
        slug: row.slug,
        displayName: row.displayName,
        config: row.config,
        createdAt: row.createdAt.toISOString(),
        updatedAt: row.updatedAt.toISOString()
      }
    };
  }

  async updateTenantConfig(options: UpdateTenantConfigOptions): Promise<TenantAdminResult> {
    // 1. Strict Schema Validation
    const validation = TenantConfigSchema.safeParse(options.config);
    if (!validation.success) {
      return {
        ok: false,
        error: 'Invalid TenantConfig schema.',
        issues: validation.error.issues
      };
    }

    const validatedConfig = validation.data;

    // 2. Fetch existing tenant
    const existing = await this.tenantRepo.getById(options.tenantId);
    if (!existing) {
      return { ok: false, error: `Tenant "${options.tenantId}" not found.` };
    }

    // 3. Optimistic Version Check (if expectedVersion specified)
    if (
      options.expectedVersion !== undefined &&
      existing.config.version !== options.expectedVersion
    ) {
      return {
        ok: false,
        error: `Conflict: Expected version ${options.expectedVersion}, but current version is ${existing.config.version}.`
      };
    }

    // 4. Auto-increment configuration version
    const nextVersion = (existing.config.version ?? 1) + 1;
    const configToPersist: TenantConfig = {
      ...validatedConfig,
      version: nextVersion
    };

    const updatedDisplayName = options.displayName || existing.displayName;

    const row = await this.tenantRepo.upsert({
      id: existing.id,
      slug: existing.slug,
      displayName: updatedDisplayName,
      config: configToPersist
    });

    return {
      ok: true,
      tenant: {
        id: row.id,
        slug: row.slug,
        displayName: row.displayName,
        config: row.config,
        createdAt: row.createdAt.toISOString(),
        updatedAt: row.updatedAt.toISOString()
      }
    };
  }
}
