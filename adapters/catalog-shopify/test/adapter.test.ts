import { describe, it, expect, vi } from 'vitest';
import { ShopifyCatalogSource, type ShopifyProduct } from '../src/index.js';

describe('Shopify Catalog Adapter (WP-31)', () => {
  const mockShopifyProducts: ShopifyProduct[] = [
    {
      id: 101,
      title: 'Camisola de Lã Merino',
      body_html: '<p>Camisola 100% lã merino de corte regular.</p>',
      vendor: 'Rewilt Apparel',
      product_type: 'Vestuário',
      handle: 'camisola-la-merino',
      status: 'active',
      tags: 'inverno, la, premium',
      variants: [
        {
          id: 201,
          title: 'Azul / M',
          price: '89.90',
          sku: 'CAM-LA-01',
          available: true
        }
      ]
    },
    {
      id: 102,
      title: 'Botas em Pele Genuína',
      body_html: '<p>Botas resistentes à água feitas à mão em Portugal.</p>',
      vendor: 'Rewilt Footwear',
      product_type: 'Calçado',
      handle: 'botas-pele-genuina',
      status: 'active',
      tags: 'calcado, couro, botas',
      variants: [
        {
          id: 202,
          title: 'Castanho / 42',
          price: '145.00',
          sku: 'BOT-PEL-02',
          available: true
        }
      ]
    }
  ];

  it('verifies connection and maps sample Shopify products', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ products: mockShopifyProducts })
    });

    const source = new ShopifyCatalogSource(mockFetch as unknown as typeof fetch);

    const res = await source.verify({
      tenantId: '00000000-0000-4000-8000-000000000001',
      shopDomain: 'loja-teste.myshopify.com',
      adminAccessToken: 'shpat_test_token_123',
      defaultCurrency: 'EUR'
    });

    expect(res.ok).toBe(true);
    expect(res.itemCount).toBe(2);
    expect(res.sample.length).toBe(2);
    expect(res.sample[0]?.sku).toBe('CAM-LA-01');
    expect(res.sample[0]?.priceMinor).toBe(8990); // €89.90
    expect(res.sample[0]?.url).toBe('https://loja-teste.myshopify.com/products/camisola-la-merino');
    expect(res.sample[0]?.description).toBe('Camisola 100% lã merino de corte regular.');
  });

  it('fetches full Shopify product catalog', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ products: mockShopifyProducts })
    });

    const source = new ShopifyCatalogSource(mockFetch as unknown as typeof fetch);

    const catalog = await source.fetch({
      tenantId: '00000000-0000-4000-8000-000000000001',
      shopDomain: 'loja-teste.myshopify.com',
      adminAccessToken: 'shpat_test_token_123',
      defaultCurrency: 'EUR'
    });

    expect(catalog.sourceKind).toBe('shopify');
    expect(catalog.items.length).toBe(2);
    expect(catalog.items[1]?.sku).toBe('BOT-PEL-02');
    expect(catalog.items[1]?.priceMinor).toBe(14500); // €145.00
  });
});
