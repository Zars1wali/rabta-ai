import { z } from 'zod';
import {
  type Catalog,
  type CatalogItem,
  type CatalogSource,
  type VerifyResult,
  CatalogItemSchema
} from '@salesops/types';

export const WooCommerceSourceConfigSchema = z.object({
  tenantId: z.string().uuid('tenantId must be a valid UUID'),
  baseUrl: z.string().url('baseUrl must be a valid URL'),
  consumerKey: z.string().min(1, 'consumerKey is required'),
  consumerSecret: z.string().min(1, 'consumerSecret is required'),
  defaultCurrency: z.enum(['EUR', 'USD', 'GBP', 'CHF']).default('EUR'),
  perPage: z.number().int().min(1).max(100).default(100),
  includeDrafts: z.boolean().default(false)
});
export type WooCommerceSourceConfig = z.infer<typeof WooCommerceSourceConfigSchema>;

export interface WooCommerceProduct {
  id: number;
  name: string;
  slug: string;
  permalink: string;
  sku: string;
  price: string;
  regular_price: string;
  sale_price: string;
  description: string;
  short_description: string;
  categories: Array<{ id: number; name: string; slug: string }>;
  stock_status: string; // 'instock' | 'outofstock' | 'onbackorder'
  status: string; // 'publish' | 'draft' | 'private'
  attributes?: Array<{ id: number; name: string; options: string[] }>;
}

export class WooCommerceCatalogSource implements CatalogSource {
  readonly kind = 'woocommerce';

  constructor(private fetchFn: typeof fetch = globalThis.fetch) {}

  supportsWebhooks(): boolean {
    return true;
  }

  async verify(cfg: unknown): Promise<VerifyResult> {
    const configResult = WooCommerceSourceConfigSchema.safeParse(cfg);
    if (!configResult.success) {
      return {
        ok: false,
        itemCount: 0,
        sample: [],
        warnings: [`Invalid WooCommerce configuration: ${configResult.error.message}`]
      };
    }

    const config = configResult.data;

    try {
      const url = new URL('/wp-json/wc/v3/products', config.baseUrl);
      url.searchParams.set('per_page', '5');
      if (!config.includeDrafts) {
        url.searchParams.set('status', 'publish');
      }

      const res = await this.fetchFn(url.toString(), {
        headers: {
          Authorization: this.buildBasicAuthHeader(config.consumerKey, config.consumerSecret),
          'User-Agent': 'SalesOps-WooCommerce-Adapter/1.0',
          Accept: 'application/json'
        }
      });

      if (!res.ok) {
        return {
          ok: false,
          itemCount: 0,
          sample: [],
          warnings: [`WooCommerce API error: ${res.status} ${res.statusText}`]
        };
      }

      const rawProducts = (await res.json()) as WooCommerceProduct[];
      if (!Array.isArray(rawProducts)) {
        return {
          ok: false,
          itemCount: 0,
          sample: [],
          warnings: ['WooCommerce response was not an array of products.']
        };
      }

      const items: CatalogItem[] = [];
      const warnings: string[] = [];

      for (const p of rawProducts) {
        const item = this.mapWooCommerceProductToCatalogItem(p, config);
        const parsed = CatalogItemSchema.safeParse(item);
        if (parsed.success) {
          items.push(parsed.data);
        } else {
          warnings.push(`Product #${p.id} (${p.name}): ${parsed.error.issues.map((i) => i.message).join(', ')}`);
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
        warnings: [`Failed to connect to WooCommerce store: ${(err as Error).message}`]
      };
    }
  }

  async fetch(cfg: unknown): Promise<Catalog> {
    const config = WooCommerceSourceConfigSchema.parse(cfg);
    const allItems: CatalogItem[] = [];
    let page = 1;
    let hasMore = true;

    while (hasMore) {
      const url = new URL('/wp-json/wc/v3/products', config.baseUrl);
      url.searchParams.set('per_page', config.perPage.toString());
      url.searchParams.set('page', page.toString());
      if (!config.includeDrafts) {
        url.searchParams.set('status', 'publish');
      }

      const res = await this.fetchFn(url.toString(), {
        headers: {
          Authorization: this.buildBasicAuthHeader(config.consumerKey, config.consumerSecret),
          'User-Agent': 'SalesOps-WooCommerce-Adapter/1.0',
          Accept: 'application/json'
        }
      });

      if (!res.ok) {
        throw new Error(`WooCommerce API fetch failed with status ${res.status}: ${res.statusText}`);
      }

      const rawProducts = (await res.json()) as WooCommerceProduct[];
      if (!Array.isArray(rawProducts) || rawProducts.length === 0) {
        hasMore = false;
        break;
      }

      for (const p of rawProducts) {
        const item = this.mapWooCommerceProductToCatalogItem(p, config);
        const parsed = CatalogItemSchema.safeParse(item);
        if (parsed.success) {
          allItems.push(parsed.data);
        }
      }

      if (rawProducts.length < config.perPage) {
        hasMore = false;
      } else {
        page++;
      }
    }

    if (allItems.length === 0) {
      throw new Error('WooCommerce store returned 0 valid products.');
    }

    return {
      tenantId: config.tenantId,
      items: allItems,
      fetchedAt: new Date().toISOString(),
      sourceKind: this.kind
    };
  }

  private mapWooCommerceProductToCatalogItem(
    p: WooCommerceProduct,
    config: WooCommerceSourceConfig
  ): CatalogItem {
    const rawPrice = p.price || p.regular_price || '0';
    const priceMinor = Math.round(parseFloat(rawPrice || '0') * 100);
    const sku = p.sku?.trim() || `wc_prod_${p.id}`;
    const category = p.categories?.[0]?.name || 'Geral';
    const description = this.stripHtml(p.short_description || p.description || p.name);
    const available = p.stock_status !== 'outofstock' && p.status === 'publish';

    const attributes: Record<string, string> = {};
    if (p.attributes) {
      for (const attr of p.attributes) {
        if (attr.name && attr.options?.length) {
          attributes[attr.name] = attr.options.join(', ');
        }
      }
    }

    return {
      sku,
      name: p.name,
      category,
      description,
      priceMinor,
      currency: config.defaultCurrency,
      billing: 'month',
      available,
      url: p.permalink || null,
      attributes
    };
  }

  private stripHtml(html: string): string {
    return html.replace(/<[^>]*>?/gm, '').trim();
  }

  private buildBasicAuthHeader(key: string, secret: string): string {
    const token = Buffer.from(`${key}:${secret}`).toString('base64');
    return `Basic ${token}`;
  }
}
