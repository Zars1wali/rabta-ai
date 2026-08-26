import { z } from 'zod';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';

export const CaptureLeadInputSchema = z.object({
  name: z.string().optional().describe('Contact person name'),
  email: z.string().email().optional().describe('Contact email address'),
  phone: z.string().optional().describe('Contact phone number'),
  companyUrl: z.string().url().optional().describe('Company website'),
  notes: z.string().optional().describe('Summary of requirements or conversation highlights')
});

export const captureLeadTool: AgentTool<typeof CaptureLeadInputSchema> = {
  name: 'capture_lead',
  description: 'Record qualified merchant lead and contact information. Strictly requires prior visitor consent.',
  schema: CaptureLeadInputSchema,
  declaration: {
    name: 'capture_lead',
    description: 'Record qualified merchant lead and contact information. Strictly requires prior visitor consent.',
    parameters: {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Contact person name' },
        email: { type: 'string', description: 'Contact email address' },
        phone: { type: 'string', description: 'Contact phone number' },
        companyUrl: { type: 'string', description: 'Company website' },
        notes: { type: 'string', description: 'Summary of requirements or conversation highlights' }
      }
    }
  },
  async execute(args, ctx: ToolExecutionContext): Promise<ToolExecutionOutput> {
    // 1. Strict Consent Check against session in DB
    const session = await ctx.sessionRepo.getSession(ctx.tenantId, ctx.sessionId);
    if (!session || !session.consentAt) {
      return {
        ok: false,
        result: {
          error:
            'Lead capture rejected: explicit visitor consent (consent_at) is required before storing contact details.',
          consentRequired: true
        }
      };
    }

    // 2. Persist lead
    const lead = await ctx.leadRepo.createLead({
      tenantId: ctx.tenantId,
      sessionId: ctx.sessionId,
      name: args.name ?? null,
      email: args.email ?? null,
      phone: args.phone ?? null,
      companyUrl: args.companyUrl ?? null,
      notes: args.notes ?? null,
      consentAt: session.consentAt
    });

    return {
      ok: true,
      result: {
        leadId: lead.id,
        capturedAt: lead.createdAt,
        status: 'recorded'
      },
      event: {
        type: 'lead_captured',
        leadId: lead.id
      }
    };
  }
};
