import { z } from 'zod';
import {
  type Catalog,
  type CatalogItem,
  type CatalogSource,
  type VerifyResult,
  CatalogItemSchema
} from '@salesops/types';

export const ShopifySourceConfigSchema = z.object({
  tenantId: z.string().uuid('tenantId must be a valid UUID'),
  shopDomain: z.string().min(1, 'shopDomain is required'), // e.g. "my-store.myshopify.com"
  adminAccessToken: z.string().min(1, 'adminAccessToken is required'),
  apiVersion: z.string().default('2024-07'),
  defaultCurrency: z.enum(['EUR', 'USD', 'GBP', 'CHF']).default('EUR'),
  limit: z.number().int().min(1).max(250).default(50)
});
export type ShopifySourceConfig = z.infer<typeof ShopifySourceConfigSchema>;

export interface ShopifyProduct {
  id: number;
  title: string;
  body_html: string;
  vendor: string;
  product_type: string;
  handle: string;
  status: string; // 'active' | 'archived' | 'draft'
  tags: string;
  variants: Array<{
    id: number;
    title: string;
    price: string;
    sku: string;
    inventory_quantity?: number;
    available?: boolean;
  }>;
}

export class ShopifyCatalogSource implements CatalogSource {
  readonly kind = 'shopify';

  constructor(private fetchFn: typeof fetch = globalThis.fetch) {}

  supportsWebhooks(): boolean {
    return true;
  }

  async verify(cfg: unknown): Promise<VerifyResult> {
    const configResult = ShopifySourceConfigSchema.safeParse(cfg);
    if (!configResult.success) {
      return {
        ok: false,
        itemCount: 0,
        sample: [],
        warnings: [`Invalid Shopify configuration: ${configResult.error.message}`]
      };
    }

    const config = configResult.data;
    const cleanDomain = config.shopDomain.replace(/^https?:\/\//, '').replace(/\/$/, '');

    try {
      const url = `https://${cleanDomain}/admin/api/${config.apiVersion}/products.json?limit=5&status=active`;
      const res = await this.fetchFn(url, {
        headers: {
          'X-Shopify-Access-Token': config.adminAccessToken,
          'Content-Type': 'application/json',
          'User-Agent': 'SalesOps-Shopify-Adapter/1.0'
        }
      });

      if (!res.ok) {
        return {
          ok: false,
          itemCount: 0,
          sample: [],
          warnings: [`Shopify API error: ${res.status} ${res.statusText}`]
        };
      }

      const data = (await res.json()) as { products?: ShopifyProduct[] };
      const rawProducts = data?.products || [];

      if (!Array.isArray(rawProducts)) {
        return {
          ok: false,
          itemCount: 0,
          sample: [],
          warnings: ['Shopify response did not contain products array.']
        };
      }

      const items: CatalogItem[] = [];
      const warnings: string[] = [];

      for (const p of rawProducts) {
        const item = this.mapShopifyProductToCatalogItem(p, config, cleanDomain);
        const parsed = CatalogItemSchema.safeParse(item);
        if (parsed.success) {
          items.push(parsed.data);
        } else {
          warnings.push(`Product #${p.id} (${p.title}): ${parsed.error.issues.map((i) => i.message).join(', ')}`);
        }
      }

      return {
        ok: items.length > 0,
        itemCount: items.length,
        sample: items.slice(0, 5),
        warnings
      };
    } catch (err: unknown) {
      return {
        ok: false,
        itemCount: 0,
        sample: [],
        warnings: [`Failed to connect to Shopify store: ${(err as Error).message}`]
      };
    }
  }

  async fetch(cfg: unknown): Promise<Catalog> {
    const config = ShopifySourceConfigSchema.parse(cfg);
    const cleanDomain = config.shopDomain.replace(/^https?:\/\//, '').replace(/\/$/, '');
    const allItems: CatalogItem[] = [];

    const url = `https://${cleanDomain}/admin/api/${config.apiVersion}/products.json?limit=${config.limit}&status=active`;
    const res = await this.fetchFn(url, {
      headers: {
        'X-Shopify-Access-Token': config.adminAccessToken,
        'Content-Type': 'application/json',
        'User-Agent': 'SalesOps-Shopify-Adapter/1.0'
      }
    });

    if (!res.ok) {
      throw new Error(`Shopify API fetch failed with status ${res.status}: ${res.statusText}`);
    }

    const data = (await res.json()) as { products?: ShopifyProduct[] };
    const rawProducts = data?.products || [];

    for (const p of rawProducts) {
      const item = this.mapShopifyProductToCatalogItem(p, config, cleanDomain);
      const parsed = CatalogItemSchema.safeParse(item);
      if (parsed.success) {
        allItems.push(parsed.data);
      }
    }

    if (allItems.length === 0) {
      throw new Error('Shopify store returned 0 valid products.');
    }

    return {
      tenantId: config.tenantId,
      items: allItems,
      fetchedAt: new Date().toISOString(),
      sourceKind: this.kind
    };
  }

  private mapShopifyProductToCatalogItem(
    p: ShopifyProduct,
    config: ShopifySourceConfig,
    cleanDomain: string
  ): CatalogItem {
    const firstVariant = p.variants?.[0];
    const rawPrice = firstVariant?.price || '0';
    const priceMinor = Math.round(parseFloat(rawPrice || '0') * 100);
    const sku = firstVariant?.sku?.trim() || `sh_${p.id}`;
    const category = p.product_type || 'Geral';
    const description = this.stripHtml(p.body_html || p.title);
    const available = p.status === 'active';

    const attributes: Record<string, string> = {
      vendor: p.vendor || ''
    };

    if (p.variants && p.variants.length > 1) {
      attributes.variants = p.variants.map((v) => `${v.title}: ${v.price}`).join(' | ');
    }

    return {
      sku,
      name: p.title,
      category,
      description,
      priceMinor,
      currency: config.defaultCurrency,
      billing: 'once',
      available,
      url: `https://${cleanDomain}/products/${p.handle}`,
      attributes
    };
  }

  private stripHtml(html: string): string {
    return html.replace(/<[^>]*>?/gm, '').trim();
  }
}
