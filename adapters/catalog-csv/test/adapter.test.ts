import { describe, it, expect } from 'vitest';
import { CsvCatalogSource, type CsvSourceConfig } from '../src/index.js';

describe('CsvCatalogSource Adapter (WP-15)', () => {
  const adapter = new CsvCatalogSource();
  const tenantId = '00000000-0000-4000-8000-000000000001';

  const validCsv = `SKU,Name,Price,Category,Description,Available
salesops_lite,"Sales Ops Lite",29.00,Planos,"Plano Lite para pequenas lojas",true
salesops_std,"Sales Ops Standard",79.00,Planos,"Plano padrão completo",true
salesops_eu,"Sales Ops Europe",99.00,Planos,"Plano Europe com RGPD e UE",true
salesops_prem,"Sales Ops Premium",199.00,Planos,"Plano premium com suporte prioritário",true
salesops_prev,"Demonstração Personalizada",50.00,Serviços,"Demo creditada",true
salesops_out,"Produto Esgotado",10.00,Planos,"Indisponível",false`;

  it('verifies CSV and returns 5 sample items and valid count', async () => {
    const config: CsvSourceConfig = {
      tenantId,
      csvData: validCsv,
      delimiter: ',',
      defaultCurrency: 'EUR',
      columnMapping: {
        sku: 'SKU',
        name: 'Name',
        price: 'Price',
        category: 'Category',
        description: 'Description',
        currency: 'currency',
        url: 'url',
        available: 'Available'
      }
    };

    const res = await adapter.verify(config);
    expect(res.ok).toBe(true);
    expect(res.itemCount).toBe(6);
    expect(res.sample.length).toBe(5);
    expect(res.sample[0]?.sku).toBe('salesops_lite');
    expect(res.sample[0]?.priceMinor).toBe(2900);
    expect(res.sample[1]?.priceMinor).toBe(7900);
  });

  it('fetches full normalized catalog with correct price minor units', async () => {
    const config: CsvSourceConfig = {
      tenantId,
      csvData: validCsv,
      delimiter: ',',
      defaultCurrency: 'EUR',
      columnMapping: {
        sku: 'SKU',
        name: 'Name',
        price: 'Price',
        category: 'Category',
        description: 'Description',
        currency: 'currency',
        url: 'url',
        available: 'Available'
      }
    };

    const catalog = await adapter.fetch(config);
    expect(catalog.tenantId).toBe(tenantId);
    expect(catalog.sourceKind).toBe('csv');
    expect(catalog.items.length).toBe(6);

    const outOfStock = catalog.items.find((i) => i.sku === 'salesops_out');
    expect(outOfStock?.available).toBe(false);
  });

  it('handles European comma formatted prices correctly (e.g. 79,90 €)', async () => {
    const commaCsv = `sku,name,price\nprod_1,"Produto Um","79,90 €"\nprod_2,"Produto Dois","1.250,50 €"`;
    const config: CsvSourceConfig = {
      tenantId,
      csvData: commaCsv,
      delimiter: ',',
      defaultCurrency: 'EUR',
      columnMapping: {
        sku: 'sku',
        name: 'name',
        price: 'price',
        category: 'category',
        description: 'description',
        currency: 'currency',
        url: 'url',
        available: 'available'
      }
    };

    const catalog = await adapter.fetch(config);
    expect(catalog.items[0]?.priceMinor).toBe(7990);
    expect(catalog.items[1]?.priceMinor).toBe(125050);
  });

  it('returns failure when required columns are missing', async () => {
    const badCsv = `colA,colB,colC\n1,2,3`;
    const config: CsvSourceConfig = {
      tenantId,
      csvData: badCsv,
      delimiter: ',',
      defaultCurrency: 'EUR',
      columnMapping: {
        sku: 'sku',
        name: 'name',
        price: 'price',
        category: 'category',
        description: 'description',
        currency: 'currency',
        url: 'url',
        available: 'available'
      }
    };

    const res = await adapter.verify(config);
    expect(res.ok).toBe(false);
    expect(res.warnings[0]).toContain('Required CSV columns not found');
  });
});
