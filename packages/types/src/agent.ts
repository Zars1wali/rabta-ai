import { z } from 'zod';
import { InboundMessageSchema } from './channel.js';
import { NotifyTargetSchema } from './close.js';

export const FunnelStageSchema = z.enum([
  'greet',
  'discover',
  'qualify',
  'present',
  'objection',
  'close',
  'won',
  'handoff',
  'lost'
]);
export type FunnelStage = z.infer<typeof FunnelStageSchema>;

export const AgentMessageRoleSchema = z.enum(['visitor', 'agent', 'human', 'system', 'tool']);
export type AgentMessageRole = z.infer<typeof AgentMessageRoleSchema>;

export const AgentMessageSchema = z.object({
  id: z.string().uuid().default(() => crypto.randomUUID()),
  role: AgentMessageRoleSchema,
  content: z.string(),
  mediaUrl: z.string().url().nullable().optional(),
  createdAt: z.string().datetime().default(() => new Date().toISOString())
});
export type AgentMessage = z.infer<typeof AgentMessageSchema>;

export const ResolvedToolCallSchema = z.object({
  id: z.string().uuid().default(() => crypto.randomUUID()),
  name: z.string().min(1),
  input: z.record(z.unknown()),
  output: z.record(z.unknown()),
  ok: z.boolean(),
  latencyMs: z.number().int().nonnegative(),
  createdAt: z.string().datetime().optional()
});
export type ResolvedToolCall = z.infer<typeof ResolvedToolCallSchema>;

export const AgentEventSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('checkout_url'), url: z.string().url() }),
  z.object({ type: z.literal('lead_captured'), leadId: z.string().uuid() }),
  z.object({ type: z.literal('handoff_requested'), target: NotifyTargetSchema })
]);
export type AgentEvent = z.infer<typeof AgentEventSchema>;

export const LeadSchema = z.object({
  id: z.string().uuid().default(() => crypto.randomUUID()),
  tenantId: z.string().uuid(),
  sessionId: z.string().uuid(),
  name: z.string().nullable().optional(),
  email: z.string().email().nullable().optional(),
  phone: z.string().nullable().optional(),
  companyUrl: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  consentAt: z.string().datetime(),
  createdAt: z.string().datetime().default(() => new Date().toISOString())
});
export type Lead = z.infer<typeof LeadSchema>;

export const AgentTurnInputSchema = z.object({
  sessionId: z.string().uuid(),
  tenantId: z.string().uuid(),
  message: InboundMessageSchema,
  history: z.array(AgentMessageSchema).max(15),
  stage: FunnelStageSchema,
  locale: z.string().min(2)
});
export type AgentTurnInput = z.infer<typeof AgentTurnInputSchema>;

export const AgentTurnOutputSchema = z.object({
  chunks: z.array(z.string()),
  stage: FunnelStageSchema,
  toolCalls: z.array(ResolvedToolCallSchema),
  events: z.array(AgentEventSchema),
  leadDelta: LeadSchema.partial().nullable().default(null),
  usage: z.object({
    inputTokens: z.number().int().nonnegative(),
    outputTokens: z.number().int().nonnegative(),
    costMinor: z.number().int().nonnegative()
  })
});
export type AgentTurnOutput = z.infer<typeof AgentTurnOutputSchema>;
