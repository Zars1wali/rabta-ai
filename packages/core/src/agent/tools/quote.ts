import { z } from 'zod';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';

export const QuoteInputSchema = z.object({
  skus: z.array(z.string().min(1)).min(1).describe('List of product SKUs to quote'),
  quantity: z.number().int().min(1).default(1).describe('Quantity per item (default: 1)'),
  term: z.enum(['month', 'year', 'once']).default('month').describe('Billing term for quote')
});

export const quoteTool: AgentTool<typeof QuoteInputSchema> = {
  name: 'quote',
  description: 'Calculate official price quote from active catalog. Computes exact server-side totals.',
  schema: QuoteInputSchema,
  declaration: {
    name: 'quote',
    description: 'Calculate official price quote from active catalog. Computes exact server-side totals.',
    parameters: {
      type: 'object',
      properties: {
        skus: {
          type: 'array',
          items: { type: 'string' },
          description: 'List of product SKUs to quote'
        },
        quantity: { type: 'integer', description: 'Quantity per item (default: 1)' },
        term: { type: 'string', enum: ['month', 'year', 'once'], description: 'Billing term for quote' }
      },
      required: ['skus']
    }
  },
  async execute(args, ctx: ToolExecutionContext): Promise<ToolExecutionOutput> {
    const lineItems = [];
    let totalMinor = 0;
    let currency = 'EUR';
    let hasStaleItems = false;
    let disclaimer: string | null = null;

    for (const sku of args.skus) {
      const { item, staleness } = await ctx.catalogService.getBySku(ctx.tenantId, sku);
      if (!item) {
        return {
          ok: false,
          result: {
            error: `SKU "${sku}" was not found in active catalog.`,
            notFoundSku: sku
          }
        };
      }

      currency = item.currency;
      const lineTotal = item.priceMinor * args.quantity;
      totalMinor += lineTotal;

      if (item.isStale) {
        hasStaleItems = true;
        disclaimer = item.stalenessDisclaimer || staleness.disclaimer;
      }

      lineItems.push({
        sku: item.sku,
        name: item.name,
        unitPriceMinor: item.priceMinor,
        quantity: args.quantity,
        totalMinor: lineTotal,
        billing: item.billing,
        isStale: item.isStale
      });
    }

    const formattedTotal = (totalMinor / 100).toFixed(2);

    return {
      ok: true,
      result: {
        lineItems,
        totalMinor,
        currency,
        formattedTotal: `${formattedTotal} ${currency}`,
        isStale: hasStaleItems,
        stalenessDisclaimer: disclaimer,
        legalNotice: 'Unverbindliche Richtofferte / Non-binding preliminary estimate (vorbehaltlich Bestätigung durch den Inhaber).'
      }
    };
  }
};
