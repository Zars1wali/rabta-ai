import { describe, it, expect } from 'vitest';
import { MONDAR_TENANT_CONFIG, MONDAR_CATALOG } from '../src/db/seed.js';
import { TenantConfigSchema, CatalogSchema } from '@salesops/types';

describe('Mondar Reinigungen Swiss Tenant Verification (mondar.ch)', () => {
  it('validates Mondar TenantConfig against canonical schema', () => {
    const parseResult = TenantConfigSchema.safeParse(MONDAR_TENANT_CONFIG);
    expect(parseResult.success).toBe(true);
    if (parseResult.success) {
      expect(parseResult.data.currency).toBe('CHF');
      expect(parseResult.data.locales).toContain('de-CH');
      expect(parseResult.data.timezone).toBe('Europe/Zurich');
      expect(parseResult.data.compliance.aiDisclosure).toBe(true);
      expect(parseResult.data.compliance.retentionDays).toBe(90);
    }
  });

  it('validates Mondar Catalog snapshot prices and Swiss cleaning services', () => {
    const parseResult = CatalogSchema.safeParse(MONDAR_CATALOG);
    expect(parseResult.success).toBe(true);
    if (parseResult.success) {
      expect(parseResult.data.items).toHaveLength(6);
      
      const item35 = parseResult.data.items.find(i => i.sku === 'cleaning_3_5');
      expect(item35).toBeDefined();
      expect(item35?.priceMinor).toBe(108000); // CHF 1'080.00
      expect(item35?.currency).toBe('CHF');
      expect(item35?.attributes?.guarantee).toBe('100% Abnahmegarantie');

      const item45 = parseResult.data.items.find(i => i.sku === 'cleaning_4_5');
      expect(item45?.priceMinor).toBe(135000); // CHF 1'350.00
    }
  });

  it('contains comprehensive policy terms for Swiss move-out cleaning warranty', () => {
    expect(MONDAR_TENANT_CONFIG.policy.warranty?.scope).toContain('Abnahmegarantie');
    expect(MONDAR_TENANT_CONFIG.policy.payment.methods).toContain('TWINT');
    expect(MONDAR_TENANT_CONFIG.policy.contact.humanEscalation).toBe('info@mondar.ch');
  });
});
