import { z } from 'zod';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';

export const RequestHumanInputSchema = z.object({
  reason: z.string().min(1).describe('Specific reason for escalating to a human representative')
});

export const requestHumanTool: AgentTool<typeof RequestHumanInputSchema> = {
  name: 'request_human',
  description: 'Escalate conversation to human representative and transition session stage to handoff.',
  schema: RequestHumanInputSchema,
  declaration: {
    name: 'request_human',
    description: 'Escalate conversation to human representative and transition session stage to handoff.',
    parameters: {
      type: 'object',
      properties: {
        reason: { type: 'string', description: 'Specific reason for escalating to a human representative' }
      },
      required: ['reason']
    }
  },
  async execute(args, ctx: ToolExecutionContext): Promise<ToolExecutionOutput> {
    // 1. Update session stage to 'handoff'
    await ctx.sessionRepo.updateTurn(ctx.tenantId, ctx.sessionId, {
      stage: 'handoff',
      tokensUsed: 0,
      costMinor: 0
    });

    const tenant = await ctx.tenantRepo.getById(ctx.tenantId);
    const escalationContact = tenant?.config.policy.contact.humanEscalation || 'support@rewilt.com';

    return {
      ok: true,
      result: {
        status: 'escalated',
        stage: 'handoff',
        escalationContact,
        reason: args.reason
      },
      event: {
        type: 'handoff_requested',
        target: {
          type: 'email',
          to: escalationContact
        }
      }
    };
  }
};
