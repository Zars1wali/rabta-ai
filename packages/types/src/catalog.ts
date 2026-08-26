import { z } from 'zod';

export const CurrencySchema = z.enum(['EUR', 'CHF', 'GBP', 'USD']);
export type Currency = z.infer<typeof CurrencySchema>;

export const BillingIntervalSchema = z.enum(['once', 'month', 'year']);
export type BillingInterval = z.infer<typeof BillingIntervalSchema>;

export const CatalogItemSchema = z.object({
  sku: z.string().min(1, 'SKU must not be empty'),
  name: z.string().min(1, 'Name must not be empty'),
  category: z.string().nullable(),
  description: z.string().nullable(),
  priceMinor: z.number().int().nonnegative('Price must be an integer minor unit (e.g. cents)'),
  currency: CurrencySchema,
  billing: BillingIntervalSchema.default('month'),
  attributes: z.record(z.union([z.string(), z.number(), z.boolean()])).default({}),
  available: z.boolean().default(true),
  url: z.string().url().nullable().default(null)
});
export type CatalogItem = z.infer<typeof CatalogItemSchema>;

export const CatalogSchema = z.object({
  tenantId: z.string().uuid('tenantId must be a valid UUID'),
  items: z.array(CatalogItemSchema),
  fetchedAt: z.string().datetime({ message: 'fetchedAt must be an ISO datetime string' }),
  sourceKind: z.string().min(1)
});
export type Catalog = z.infer<typeof CatalogSchema>;

export const VerifyResultSchema = z.object({
  ok: z.boolean(),
  itemCount: z.number().int().nonnegative(),
  sample: z.array(CatalogItemSchema).max(5),
  warnings: z.array(z.string())
});
export type VerifyResult = z.infer<typeof VerifyResultSchema>;

export interface CatalogSource {
  readonly kind: string;
  verify(cfg: unknown): Promise<VerifyResult>;
  fetch(cfg: unknown): Promise<Catalog>;
  supportsWebhooks(): boolean;
}
