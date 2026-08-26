import { z } from 'zod';
import fs from 'fs/promises';
import {
  type Catalog,
  type CatalogItem,
  type CatalogSource,
  type VerifyResult,
  CatalogItemSchema
} from '@salesops/types';

export const CsvColumnMappingSchema = z.object({
  sku: z.string().default('sku'),
  name: z.string().default('name'),
  category: z.string().default('category'),
  price: z.string().default('price'),
  currency: z.string().default('currency'),
  description: z.string().default('description'),
  url: z.string().default('url'),
  available: z.string().default('available')
});
export type CsvColumnMapping = z.infer<typeof CsvColumnMappingSchema>;

export const CsvSourceConfigSchema = z.object({
  tenantId: z.string().uuid('tenantId must be a valid UUID'),
  csvData: z.string().optional(),
  filePath: z.string().optional(),
  url: z.string().url().optional(),
  delimiter: z.string().default(','),
  defaultCurrency: z.enum(['EUR', 'USD', 'GBP', 'CHF']).default('EUR'),
  columnMapping: CsvColumnMappingSchema.default({
    sku: 'sku',
    name: 'name',
    category: 'category',
    price: 'price',
    currency: 'currency',
    description: 'description',
    url: 'url',
    available: 'available'
  })
});
export type CsvSourceConfig = z.infer<typeof CsvSourceConfigSchema>;

export class CsvCatalogSource implements CatalogSource {
  readonly kind = 'csv';

  supportsWebhooks(): boolean {
    return false;
  }

  async verify(cfg: unknown): Promise<VerifyResult> {
    const configResult = CsvSourceConfigSchema.safeParse(cfg);
    if (!configResult.success) {
      return {
        ok: false,
        itemCount: 0,
        sample: [],
        warnings: [`Invalid CSV source configuration: ${configResult.error.message}`]
      };
    }

    try {
      const items = await this.parseCsvItems(configResult.data);
      const sample = items.slice(0, 5);

      return {
        ok: items.length > 0,
        itemCount: items.length,
        sample,
        warnings: items.length === 0 ? ['CSV file contains no valid items.'] : []
      };
    } catch (err: unknown) {
      return {
        ok: false,
        itemCount: 0,
        sample: [],
        warnings: [`Failed to verify CSV source: ${(err as Error).message}`]
      };
    }
  }

  async fetch(cfg: unknown): Promise<Catalog> {
    const config = CsvSourceConfigSchema.parse(cfg);
    const items = await this.parseCsvItems(config);

    if (items.length === 0) {
      throw new Error('CSV catalog source contained 0 valid items.');
    }

    return {
      tenantId: config.tenantId,
      items,
      fetchedAt: new Date().toISOString(),
      sourceKind: this.kind
    };
  }

  private async parseCsvItems(config: CsvSourceConfig): Promise<CatalogItem[]> {
    const content = await this.extractRawCsv(config);
    const rows = this.parseCsvString(content, config.delimiter);
    if (rows.length < 2) return [];

    const headers = rows[0]!.map((h) => h.trim().toLowerCase());
    const mapping = config.columnMapping;

    const findColIndex = (mappedName: string) => {
      const target = mappedName.toLowerCase();
      return headers.findIndex((h) => h === target);
    };

    const skuIdx = findColIndex(mapping.sku);
    const nameIdx = findColIndex(mapping.name);
    const priceIdx = findColIndex(mapping.price);
    const catIdx = findColIndex(mapping.category);
    const descIdx = findColIndex(mapping.description);
    const urlIdx = findColIndex(mapping.url);
    const availIdx = findColIndex(mapping.available);

    if (skuIdx === -1 || nameIdx === -1 || priceIdx === -1) {
      throw new Error(
        `Required CSV columns not found. Headers: [${headers.join(', ')}]. Mappings: sku='${mapping.sku}', name='${mapping.name}', price='${mapping.price}'`
      );
    }

    const items: CatalogItem[] = [];

    for (let r = 1; r < rows.length; r++) {
      const row = rows[r]!;
      if (row.length === 0 || (row.length === 1 && !row[0]?.trim())) continue;

      const sku = row[skuIdx]?.trim();
      const name = row[nameIdx]?.trim();
      const rawPrice = row[priceIdx]?.trim();

      if (!sku || !name || !rawPrice) continue;

      const priceMinor = this.parsePriceToMinor(rawPrice);
      const category = (catIdx !== -1 ? row[catIdx]?.trim() : '') || 'Geral';
      const description = (descIdx !== -1 ? row[descIdx]?.trim() : '') || name;
      const url = urlIdx !== -1 && row[urlIdx]?.trim() ? row[urlIdx]?.trim() : undefined;
      const availRaw = availIdx !== -1 ? row[availIdx]?.trim().toLowerCase() : 'true';
      const available = availRaw !== 'false' && availRaw !== '0' && availRaw !== 'outofstock';

      const candidate = {
        sku,
        name,
        category,
        description,
        priceMinor,
        currency: config.defaultCurrency,
        billing: 'month' as const,
        available,
        url: url && (url.startsWith('http://') || url.startsWith('https://')) ? url : null
      };

      const parsed = CatalogItemSchema.safeParse(candidate);
      if (parsed.success) {
        items.push(parsed.data);
      }
    }

    return items;
  }

  private parsePriceToMinor(raw: string): number {
    // Strips currency symbols: e.g. "€ 79,90" -> 7990
    const cleaned = raw.replace(/[^0-9.,]/g, '').trim();
    if (!cleaned) return 0;

    if (cleaned.includes(',') && cleaned.includes('.')) {
      // European format: 1.234,56
      const normalized = cleaned.replace(/\./g, '').replace(',', '.');
      return Math.round(parseFloat(normalized) * 100);
    }

    if (cleaned.includes(',')) {
      // 79,90 -> 79.90
      const normalized = cleaned.replace(',', '.');
      return Math.round(parseFloat(normalized) * 100);
    }

    const val = parseFloat(cleaned);
    // If integer and large (e.g. 7900), check if already minor units or float
    if (cleaned.includes('.')) {
      return Math.round(val * 100);
    }
    return Math.round(val * 100);
  }

  private parseCsvString(text: string, delimiter = ','): string[][] {
    const lines: string[][] = [];
    let currentRow: string[] = [];
    let currentCell = '';
    let inQuotes = false;

    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      const nextChar = text[i + 1];

      if (char === '"') {
        if (inQuotes && nextChar === '"') {
          currentCell += '"';
          i++; // Skip escaped quote
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === delimiter && !inQuotes) {
        currentRow.push(currentCell);
        currentCell = '';
      } else if ((char === '\r' || char === '\n') && !inQuotes) {
        if (char === '\r' && nextChar === '\n') i++;
        currentRow.push(currentCell);
        lines.push(currentRow);
        currentRow = [];
        currentCell = '';
      } else {
        currentCell += char;
      }
    }

    if (currentCell || currentRow.length > 0) {
      currentRow.push(currentCell);
      lines.push(currentRow);
    }

    return lines;
  }

  private async extractRawCsv(config: CsvSourceConfig): Promise<string> {
    if (config.csvData) {
      return config.csvData;
    }

    if (config.filePath) {
      return await fs.readFile(config.filePath, 'utf-8');
    }

    if (config.url) {
      const res = await fetch(config.url);
      if (!res.ok) {
        throw new Error(`HTTP fetch failed with status ${res.status} ${res.statusText}`);
      }
      return await res.text();
    }

    throw new Error('No CSV source provided (must specify csvData, filePath, or url).');
  }
}
