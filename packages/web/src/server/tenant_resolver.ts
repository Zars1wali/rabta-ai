import type { TenantRepository, tenants } from '@salesops/core';
import type { TenantConfig } from '@salesops/types';

export type TenantRecord = typeof tenants.$inferSelect;

export interface TenantResolutionResult {
  ok: boolean;
  tenant?: TenantRecord;
  error?: string;
  statusCode?: number;
}

export async function resolveTenantByOrigin(
  originHeader: string | null | undefined,
  tenantRepo: TenantRepository,
  allTenantsProvider?: () => Promise<TenantRecord[]>
): Promise<TenantResolutionResult> {
  if (!originHeader) {
    return {
      ok: false,
      error: 'Missing Origin header. An origin is required to resolve tenant context.',
      statusCode: 403
    };
  }

  let normalizedOrigin: string;
  try {
    const url = new URL(originHeader);
    normalizedOrigin = url.origin.toLowerCase();
  } catch {
    normalizedOrigin = originHeader.trim().toLowerCase();
  }

  // If a provider function is supplied (or in-memory cache), query all tenants
  const tenantList = allTenantsProvider ? await allTenantsProvider() : [];

  for (const tenant of tenantList) {
    const config = tenant.config as TenantConfig;
    if (config.channels && Array.isArray(config.channels)) {
      for (const ch of config.channels) {
        if (ch.kind === 'web' && Array.isArray(ch.allowedOrigins)) {
          const isAllowed = ch.allowedOrigins.some((allowed) => {
            try {
              const allowedUrl = new URL(allowed);
              return allowedUrl.origin.toLowerCase() === normalizedOrigin;
            } catch {
              return allowed.toLowerCase() === normalizedOrigin;
            }
          });

          if (isAllowed) {
            return {
              ok: true,
              tenant
            };
          }
        }
      }
    }
  }

  return {
    ok: false,
    error: `Origin "${normalizedOrigin}" is not registered for any active tenant.`,
    statusCode: 403
  };
}
