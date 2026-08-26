import { z } from 'zod';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';

export const CreatePreviewCheckoutInputSchema = z.object({
  email: z.string().email().describe('Merchant contact email for preview setup'),
  shopUrl: z.string().url().describe('Merchant website or store URL containing their product catalog'),
  locale: z.string().default('pt-PT').describe('Language for checkout session')
});

export const createPreviewCheckoutTool: AgentTool<typeof CreatePreviewCheckoutInputSchema> = {
  name: 'create_preview_checkout',
  description: 'Create a 50 EUR paid store preview checkout for custom demo on merchant catalog (100% credited on subscription).',
  schema: CreatePreviewCheckoutInputSchema,
  declaration: {
    name: 'create_preview_checkout',
    description: 'Create a 50 EUR paid store preview checkout for custom demo on merchant catalog (100% credited on subscription).',
    parameters: {
      type: 'object',
      properties: {
        email: { type: 'string', description: 'Merchant contact email for preview setup' },
        shopUrl: { type: 'string', description: 'Merchant website or store URL containing their product catalog' },
        locale: { type: 'string', description: 'Language for checkout session' }
      },
      required: ['email', 'shopUrl']
    }
  },
  async execute(args, ctx: ToolExecutionContext): Promise<ToolExecutionOutput> {
    const previewPriceMinor = 5000;
    let url: string;

    if (ctx.stripeCheckoutCreator) {
      url = await ctx.stripeCheckoutCreator({
        tenantId: ctx.tenantId,
        sessionId: ctx.sessionId,
        sku: 'salesops_preview',
        email: args.email,
        locale: args.locale,
        mode: 'payment',
        priceMinor: previewPriceMinor
      });
    } else {
      url = `https://checkout.stripe.com/pay/cs_live_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}?kind=preview&email=${encodeURIComponent(args.email)}`;
    }

    return {
      ok: true,
      result: {
        checkoutUrl: url,
        priceMinor: previewPriceMinor,
        currency: 'EUR',
        creditedOnConversion: true,
        merchantShopUrl: args.shopUrl
      },
      event: {
        type: 'checkout_url',
        url
      }
    };
  }
};
