import { z } from 'zod';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';

export const SearchCatalogInputSchema = z.object({
  query: z.string().optional().describe('Search terms or keywords matching products or services'),
  category: z.string().optional().describe('Filter by product category'),
  maxPriceMinor: z.number().int().nonnegative().optional().describe('Maximum price in minor units (e.g. 5000 for 50.00 EUR)'),
  limit: z.number().int().min(1).max(20).default(5).describe('Maximum number of items to return')
});

export const searchCatalogTool: AgentTool<typeof SearchCatalogInputSchema> = {
  name: 'search_catalog',
  description: 'Search active product catalog by keywords, category, or price range. Returns verified items or empty list.',
  schema: SearchCatalogInputSchema,
  declaration: {
    name: 'search_catalog',
    description: 'Search active product catalog by keywords, category, or price range. Returns verified items or empty list.',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search terms or keywords matching products or services' },
        category: { type: 'string', description: 'Filter by product category' },
        maxPriceMinor: { type: 'integer', description: 'Maximum price in minor units (e.g. 5000 for 50.00 EUR)' },
        limit: { type: 'integer', description: 'Maximum number of items to return' }
      }
    }
  },
  async execute(args, ctx: ToolExecutionContext): Promise<ToolExecutionOutput> {
    const searchResult = await ctx.catalogService.search(ctx.tenantId, {
      query: args.query,
      category: args.category,
      maxPriceMinor: args.maxPriceMinor,
      limit: args.limit
    });

    return {
      ok: true,
      result: {
        items: searchResult.items.map((item) => ({
          sku: item.sku,
          name: item.name,
          category: item.category,
          description: item.description,
          priceMinor: item.priceMinor,
          currency: item.currency,
          billing: item.billing,
          available: item.available,
          url: item.url,
          isStale: item.isStale,
          stalenessDisclaimer: item.stalenessDisclaimer
        })),
        totalFound: searchResult.items.length,
        stalenessState: searchResult.staleness.state
      }
    };
  }
};
