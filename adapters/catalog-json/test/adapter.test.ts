import { describe, it, expect } from 'vitest';
import { JsonCatalogSource } from '../src/index.js';

describe('JsonCatalogSource Adapter', () => {
  const adapter = new JsonCatalogSource();
  const tenantId = '550e8400-e29b-41d4-a716-446655440000';

  const mockItems = Array.from({ length: 8 }, (_, i) => ({
    sku: `SKU-00${i + 1}`,
    name: `Product ${i + 1}`,
    category: i % 2 === 0 ? 'Footwear' : 'Apparel',
    description: `Description for product ${i + 1}`,
    priceMinor: (i + 1) * 1000,
    currency: 'EUR' as const,
    billing: 'once' as const,
    attributes: { size: 'M' },
    available: true,
    url: `https://store.pt/products/sku-00${i + 1}`
  }));

  it('supportsWebhooks returns false', () => {
    expect(adapter.supportsWebhooks()).toBe(false);
  });

  it('verifies valid in-memory items and samples exactly 5 items', async () => {
    const result = await adapter.verify({
      tenantId,
      items: mockItems
    });

    expect(result.ok).toBe(true);
    expect(result.itemCount).toBe(8);
    expect(result.sample.length).toBe(5);
    expect(result.sample[0]?.sku).toBe('SKU-001');
    expect(result.warnings.length).toBe(0);
  });

  it('verifies valid raw JSON string', async () => {
    const rawJson = JSON.stringify({ items: mockItems.slice(0, 3) });
    const result = await adapter.verify({
      tenantId,
      jsonData: rawJson
    });

    expect(result.ok).toBe(true);
    expect(result.itemCount).toBe(3);
    expect(result.sample.length).toBe(3);
  });

  it('collects warnings for invalid items (e.g. negative price or missing sku)', async () => {
    const invalidItems = [
      { sku: 'VALID-1', name: 'Valid Item', priceMinor: 1000, currency: 'EUR' },
      { sku: '', name: 'Empty SKU', priceMinor: 2000, currency: 'EUR' },
      { sku: 'INVALID-PRICE', name: 'Bad Price', priceMinor: -500, currency: 'EUR' }
    ];

    const result = await adapter.verify({
      tenantId,
      items: invalidItems
    });

    expect(result.ok).toBe(false);
    expect(result.itemCount).toBe(1);
    expect(result.sample.length).toBe(1);
    expect(result.warnings.length).toBe(2);
  });

  it('fetches valid catalog snapshot successfully', async () => {
    const catalog = await adapter.fetch({
      tenantId,
      items: mockItems
    });

    expect(catalog.tenantId).toBe(tenantId);
    expect(catalog.sourceKind).toBe('json');
    expect(catalog.items.length).toBe(8);
    expect(catalog.fetchedAt).toBeDefined();
  });

  it('throws when fetching a source with 0 valid items', async () => {
    await expect(
      adapter.fetch({
        tenantId,
        items: [{ sku: '', name: '', priceMinor: -100 }]
      })
    ).rejects.toThrow(/Catalog source contained 0 valid items/);
  });
});
