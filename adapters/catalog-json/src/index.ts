import { z } from 'zod';
import fs from 'fs/promises';
import {
  type Catalog,
  type CatalogItem,
  type CatalogSource,
  type VerifyResult,
  CatalogItemSchema
} from '@salesops/types';

export const JsonSourceConfigSchema = z.object({
  tenantId: z.string().uuid('tenantId must be a valid UUID'),
  jsonData: z.string().optional(),
  items: z.array(z.unknown()).optional(),
  filePath: z.string().optional(),
  url: z.string().url().optional()
});
export type JsonSourceConfig = z.infer<typeof JsonSourceConfigSchema>;

export class JsonCatalogSource implements CatalogSource {
  readonly kind = 'json';

  supportsWebhooks(): boolean {
    return false;
  }

  async verify(cfg: unknown): Promise<VerifyResult> {
    const configResult = JsonSourceConfigSchema.safeParse(cfg);
    if (!configResult.success) {
      return {
        ok: false,
        itemCount: 0,
        sample: [],
        warnings: [`Invalid JSON source configuration: ${configResult.error.message}`]
      };
    }

    try {
      const rawItems = await this.extractRawItems(configResult.data);
      const warnings: string[] = [];
      const validItems: CatalogItem[] = [];

      for (let i = 0; i < rawItems.length; i++) {
        const raw = rawItems[i];
        const itemResult = CatalogItemSchema.safeParse(raw);

        if (itemResult.success) {
          validItems.push(itemResult.data);
        } else {
          const itemIdentifier = (raw as Record<string, unknown>)?.sku || `Row #${i + 1}`;
          warnings.push(`Item '${itemIdentifier}' validation error: ${itemResult.error.issues.map((iss) => iss.message).join(', ')}`);
        }
      }

      const sample = validItems.slice(0, 5);

      return {
        ok: validItems.length > 0 && warnings.length === 0,
        itemCount: validItems.length,
        sample,
        warnings
      };
    } catch (err: unknown) {
      return {
        ok: false,
        itemCount: 0,
        sample: [],
        warnings: [`Failed to load JSON source: ${(err as Error).message}`]
      };
    }
  }

  async fetch(cfg: unknown): Promise<Catalog> {
    const config = JsonSourceConfigSchema.parse(cfg);
    const rawItems = await this.extractRawItems(config);
    const validItems: CatalogItem[] = [];
    const errors: string[] = [];

    for (let i = 0; i < rawItems.length; i++) {
      const raw = rawItems[i];
      const itemResult = CatalogItemSchema.safeParse(raw);

      if (itemResult.success) {
        validItems.push(itemResult.data);
      } else {
        const itemIdentifier = (raw as Record<string, unknown>)?.sku || `Row #${i + 1}`;
        errors.push(`[${itemIdentifier}]: ${itemResult.error.issues.map((iss) => iss.message).join(', ')}`);
      }
    }

    if (errors.length > 0 && validItems.length === 0) {
      throw new Error(`Catalog source contained 0 valid items. Errors: ${errors.slice(0, 5).join('; ')}`);
    }

    return {
      tenantId: config.tenantId,
      items: validItems,
      fetchedAt: new Date().toISOString(),
      sourceKind: this.kind
    };
  }

  private async extractRawItems(config: JsonSourceConfig): Promise<unknown[]> {
    if (config.items && Array.isArray(config.items)) {
      return config.items;
    }

    if (config.jsonData) {
      const parsed = JSON.parse(config.jsonData);
      return Array.isArray(parsed) ? parsed : (parsed.items || []);
    }

    if (config.filePath) {
      const content = await fs.readFile(config.filePath, 'utf-8');
      const parsed = JSON.parse(content);
      return Array.isArray(parsed) ? parsed : (parsed.items || []);
    }

    if (config.url) {
      const res = await fetch(config.url);
      if (!res.ok) {
        throw new Error(`HTTP fetch failed with status ${res.status} ${res.statusText}`);
      }
      const parsed = await res.json();
      return Array.isArray(parsed) ? parsed : (parsed.items || []);
    }

    throw new Error('No valid JSON source provided (must specify items, jsonData, filePath, or url).');
  }
}
