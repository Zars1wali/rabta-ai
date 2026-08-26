import { describe, it, expect, vi } from 'vitest';
import { WooCommerceCatalogSource, type WooCommerceSourceConfig } from '../src/index.js';

describe('WooCommerceCatalogSource Adapter (WP-15)', () => {
  const tenantId = '00000000-0000-4000-8000-000000000001';

  const mockWooProducts = [
    {
      id: 101,
      name: 'Camisa Oxford Azul',
      slug: 'camisa-oxford-azul',
      permalink: 'https://minhaloja.pt/produto/camisa-oxford-azul',
      sku: 'CAM-AZ-01',
      price: '49.90',
      regular_price: '49.90',
      sale_price: '',
      description: '<p>Camisa oxford 100% algodão.</p>',
      short_description: '<p>Corte moderno e elegante.</p>',
      categories: [{ id: 1, name: 'Vestuário', slug: 'vestuario' }],
      stock_status: 'instock',
      status: 'publish'
    },
    {
      id: 102,
      name: 'Calças Chino Bege',
      slug: 'calcas-chino-bege',
      permalink: 'https://minhaloja.pt/produto/calcas-chino-bege',
      sku: 'CAL-BE-02',
      price: '59.00',
      regular_price: '69.00',
      sale_price: '59.00',
      description: '<p>Calças de sarja confortável.</p>',
      short_description: '',
      categories: [{ id: 1, name: 'Vestuário', slug: 'vestuario' }],
      stock_status: 'outofstock',
      status: 'publish'
    }
  ];

  it('declares supportsWebhooks as true', () => {
    const adapter = new WooCommerceCatalogSource();
    expect(adapter.supportsWebhooks()).toBe(true);
    expect(adapter.kind).toBe('woocommerce');
  });

  it('verifies store connectivity and samples products with basic auth', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockWooProducts
    });

    const adapter = new WooCommerceCatalogSource(mockFetch as unknown as typeof fetch);

    const config: WooCommerceSourceConfig = {
      tenantId,
      baseUrl: 'https://minhaloja.pt',
      consumerKey: 'ck_test_12345',
      consumerSecret: 'cs_test_67890',
      defaultCurrency: 'EUR',
      perPage: 10,
      includeDrafts: false
    };

    const res = await adapter.verify(config);

    expect(res.ok).toBe(true);
    expect(res.itemCount).toBe(2);
    expect(res.sample.length).toBe(2);
    expect(res.sample[0]?.sku).toBe('CAM-AZ-01');
    expect(res.sample[0]?.priceMinor).toBe(4990);
    expect(res.sample[0]?.description).toBe('Corte moderno e elegante.');
    expect(res.sample[1]?.available).toBe(false); // outofstock

    expect(mockFetch).toHaveBeenCalledWith(
      'https://minhaloja.pt/wp-json/wc/v3/products?per_page=5&status=publish',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: expect.stringContaining('Basic ')
        })
      })
    );
  });

  it('fetches full catalog with pagination', async () => {
    let pageCount = 0;
    const mockFetch = vi.fn().mockImplementation(async () => {
      pageCount++;
      if (pageCount === 1) {
        return {
          ok: true,
          status: 200,
          json: async () => mockWooProducts
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => []
      };
    });

    const adapter = new WooCommerceCatalogSource(mockFetch as unknown as typeof fetch);

    const config: WooCommerceSourceConfig = {
      tenantId,
      baseUrl: 'https://minhaloja.pt',
      consumerKey: 'ck_test_12345',
      consumerSecret: 'cs_test_67890',
      defaultCurrency: 'EUR',
      perPage: 10,
      includeDrafts: false
    };

    const catalog = await adapter.fetch(config);

    expect(catalog.tenantId).toBe(tenantId);
    expect(catalog.sourceKind).toBe('woocommerce');
    expect(catalog.items.length).toBe(2);
  });

  it('handles WooCommerce authentication or connection errors cleanly in verify', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized'
    });

    const adapter = new WooCommerceCatalogSource(mockFetch as unknown as typeof fetch);

    const config: WooCommerceSourceConfig = {
      tenantId,
      baseUrl: 'https://minhaloja.pt',
      consumerKey: 'ck_invalid',
      consumerSecret: 'cs_invalid',
      defaultCurrency: 'EUR',
      perPage: 10,
      includeDrafts: false
    };

    const res = await adapter.verify(config);

    expect(res.ok).toBe(false);
    expect(res.warnings[0]).toContain('WooCommerce API error: 401 Unauthorized');
  });
});
