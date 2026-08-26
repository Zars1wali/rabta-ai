import { z } from 'zod';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';

export const GetPolicyInputSchema = z.object({
  topic: z
    .enum(['shipping', 'returns', 'warranty', 'payment', 'hours', 'contact', 'custom'])
    .describe('Store policy topic to query')
});

export const getPolicyTool: AgentTool<typeof GetPolicyInputSchema> = {
  name: 'get_policy',
  description: 'Retrieve verified store policy details (shipping, returns, warranty, payment methods, hours, escalation).',
  schema: GetPolicyInputSchema,
  declaration: {
    name: 'get_policy',
    description: 'Retrieve verified store policy details (shipping, returns, warranty, payment methods, hours, escalation).',
    parameters: {
      type: 'object',
      properties: {
        topic: {
          type: 'string',
          enum: ['shipping', 'returns', 'warranty', 'payment', 'hours', 'contact', 'custom'],
          description: 'Store policy topic to query'
        }
      },
      required: ['topic']
    }
  },
  async execute(args, ctx: ToolExecutionContext): Promise<ToolExecutionOutput> {
    const tenant = await ctx.tenantRepo.getById(ctx.tenantId);
    if (!tenant) {
      return {
        ok: false,
        result: { error: 'Tenant not found.' }
      };
    }

    const policy = tenant.config.policy;
    const value = policy ? policy[args.topic] : null;

    return {
      ok: true,
      result: {
        topic: args.topic,
        policy: value ?? null
      }
    };
  }
};
