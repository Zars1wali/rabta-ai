import { z } from 'zod';
import { TierSchema } from './tenant.js';

export const DepletionStateSchema = z.enum([
  'ok',
  'notice',
  'warning',
  'critical',
  'grace',
  'depleted'
]);
export type DepletionState = z.infer<typeof DepletionStateSchema>;

export const DepletionActionSchema = z.enum(['degrade', 'autotopup', 'pause']);
export type DepletionAction = z.infer<typeof DepletionActionSchema>;

export const PlanChangeKindSchema = z.enum([
  'tier_up',
  'tier_down',
  'blocks_up',
  'blocks_down',
  'cancel'
]);
export type PlanChangeKind = z.infer<typeof PlanChangeKindSchema>;

export const EntitlementSchema = z.object({
  id: z.string().uuid().default(() => crypto.randomUUID()),
  tenantId: z.string().uuid(),
  stripeSubscriptionId: z.string().min(1),
  periodStart: z.string().datetime(),
  periodEnd: z.string().datetime(),
  tier: TierSchema,
  includedConversations: z.number().int().nonnegative(),
  blockQuantity: z.number().int().nonnegative().default(0),
  blockSize: z.number().int().positive().default(1000),
  gracePercent: z.number().int().nonnegative().default(10),
  onDepletion: DepletionActionSchema.default('degrade'),
  createdAt: z.string().datetime().default(() => new Date().toISOString())
});
export type Entitlement = z.infer<typeof EntitlementSchema>;

export const UsageEventSchema = z.object({
  id: z.string().uuid().default(() => crypto.randomUUID()),
  tenantId: z.string().uuid(),
  entitlementId: z.string().uuid(),
  sessionId: z.string().uuid(),
  metric: z.literal('conversation').default('conversation'),
  channel: z.string().min(1),
  identityHash: z.string().min(1),
  windowStart: z.string().datetime(),
  counted: z.boolean().default(true),
  createdAt: z.string().datetime().default(() => new Date().toISOString())
});
export type UsageEvent = z.infer<typeof UsageEventSchema>;

export const UsageCounterSchema = z.object({
  tenantId: z.string().uuid(),
  entitlementId: z.string().uuid(),
  metric: z.string().min(1),
  used: z.number().int().nonnegative().default(0),
  updatedAt: z.string().datetime().default(() => new Date().toISOString())
});
export type UsageCounter = z.infer<typeof UsageCounterSchema>;

export const DepletionAlertSchema = z.object({
  id: z.string().uuid().default(() => crypto.randomUUID()),
  tenantId: z.string().uuid(),
  entitlementId: z.string().uuid(),
  threshold: z.union([z.literal(50), z.literal(80), z.literal(95), z.literal(100)]),
  sentAt: z.string().datetime().default(() => new Date().toISOString())
});
export type DepletionAlert = z.infer<typeof DepletionAlertSchema>;

export const PlanChangeSchema = z.object({
  id: z.string().uuid().default(() => crypto.randomUUID()),
  tenantId: z.string().uuid(),
  kind: PlanChangeKindSchema,
  fromTier: TierSchema.nullable().optional(),
  toTier: TierSchema.nullable().optional(),
  fromBlocks: z.number().int().nonnegative().nullable().optional(),
  toBlocks: z.number().int().nonnegative().nullable().optional(),
  effective: z.enum(['immediate', 'period_end']),
  effectiveAt: z.string().datetime(),
  stripeRef: z.string().nullable().optional(),
  status: z.enum(['pending', 'applied', 'failed', 'cancelled']).default('pending'),
  requestedBy: z.string().min(1),
  createdAt: z.string().datetime().default(() => new Date().toISOString())
});
export type PlanChange = z.infer<typeof PlanChangeSchema>;

export const UsageResponseSchema = z.object({
  period: z.object({
    start: z.string().datetime(),
    end: z.string().datetime(),
    daysLeft: z.number().int().nonnegative()
  }),
  tier: TierSchema,
  entitled: z.number().int().nonnegative(),
  used: z.number().int().nonnegative(),
  gracePercent: z.number().int().nonnegative(),
  state: DepletionStateSchema,
  burnPerDay: z.number().nullable(),
  depletesOn: z.string().nullable(),
  projectedUse: z.number().int().nullable(),
  recommendation: z.object({
    action: z.enum(['none', 'buy_blocks', 'tier_up', 'tier_down']),
    blocks: z.number().int().positive().optional(),
    tier: TierSchema.optional(),
    costMinor: z.number().int().nonnegative(),
    reasoning: z.string()
  }),
  series: z.array(
    z.object({
      date: z.string(),
      conversations: z.number().int().nonnegative()
    })
  ),
  onDepletion: DepletionActionSchema,
  pendingChange: PlanChangeSchema.nullable()
});
export type UsageResponse = z.infer<typeof UsageResponseSchema>;
