import { z } from 'zod';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';

export const CreateSubscriptionCheckoutInputSchema = z.object({
  sku: z.string().min(1).describe('Product or plan SKU to subscribe to'),
  email: z.string().email().optional().describe('Shopper email for prefilling checkout'),
  locale: z.string().default('pt-PT').describe('Checkout interface language')
});

export const createSubscriptionCheckoutTool: AgentTool<typeof CreateSubscriptionCheckoutInputSchema> = {
  name: 'create_subscription_checkout',
  description: 'Create a secure Stripe subscription checkout session for a recurring plan.',
  schema: CreateSubscriptionCheckoutInputSchema,
  declaration: {
    name: 'create_subscription_checkout',
    description: 'Create a secure Stripe subscription checkout session for a recurring plan.',
    parameters: {
      type: 'object',
      properties: {
        sku: { type: 'string', description: 'Product or plan SKU to subscribe to' },
        email: { type: 'string', description: 'Shopper email for prefilling checkout' },
        locale: { type: 'string', description: 'Checkout interface language' }
      },
      required: ['sku']
    }
  },
  async execute(args, ctx: ToolExecutionContext): Promise<ToolExecutionOutput> {
    const { item } = await ctx.catalogService.getBySku(ctx.tenantId, args.sku);
    if (!item) {
      return {
        ok: false,
        result: { error: `Plan "${args.sku}" is not available.` }
      };
    }

    let url: string;
    if (ctx.stripeCheckoutCreator) {
      url = await ctx.stripeCheckoutCreator({
        tenantId: ctx.tenantId,
        sessionId: ctx.sessionId,
        sku: args.sku,
        email: args.email,
        locale: args.locale,
        mode: 'subscription',
        priceMinor: item.priceMinor
      });
    } else {
      url = `https://checkout.stripe.com/pay/cs_live_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}?sku=${encodeURIComponent(args.sku)}`;
    }

    return {
      ok: true,
      result: {
        checkoutUrl: url,
        planName: item.name,
        priceMinor: item.priceMinor,
        currency: item.currency,
        billing: item.billing
      },
      event: {
        type: 'checkout_url',
        url
      }
    };
  }
};
