import { z } from 'zod';
import { CurrencySchema } from './catalog.js';
import { StorePolicySchema } from './knowledge.js';
import { CloseActionSchema } from './close.js';

export const TierSchema = z.enum(['lite', 'standard', 'europe', 'premium', 'custom']);
export type Tier = z.infer<typeof TierSchema>;

export const PersonaToneSchema = z.enum([
  'warm_direct',
  'professional_technical',
  'casual_enthusiastic',
  'concise_formal'
]);
export type PersonaTone = z.infer<typeof PersonaToneSchema>;

export const ChannelConfigWebSchema = z.object({
  kind: z.literal('web'),
  allowedOrigins: z.array(z.string().url('allowedOrigin must be a valid URL')).min(1)
});

export const ChannelConfigWhatsAppSchema = z.object({
  kind: z.literal('whatsapp'),
  phoneNumberId: z.string().min(1),
  wabaId: z.string().min(1)
});

export const ChannelConfigEmailSchema = z.object({
  kind: z.literal('email'),
  address: z.string().email()
});

export const ChannelConfigSchema = z.discriminatedUnion('kind', [
  ChannelConfigWebSchema,
  ChannelConfigWhatsAppSchema,
  ChannelConfigEmailSchema
]);
export type ChannelConfig = z.infer<typeof ChannelConfigSchema>;

export const TenantConfigSchema = z.object({
  version: z.number().int().positive().default(1),
  tenantId: z.string().uuid(),
  displayName: z.string().min(1),
  tier: TierSchema.default('standard'),
  locales: z.array(z.string().min(2)).min(1),
  currency: CurrencySchema,
  timezone: z.string().min(1).default('Europe/Lisbon'),

  persona: z.object({
    tone: PersonaToneSchema.default('warm_direct'),
    greeting: z.string().min(1),
    escalationPhrase: z.string().min(1)
  }),

  catalog: z.object({
    source: z.string().min(1),
    config: z.record(z.unknown()).default({}),
    refresh: z.object({
      mode: z.enum(['poll', 'webhook']).default('poll'),
      ttlMinutes: z.number().int().positive().default(60)
    }),
    staleness: z.object({
      maxAgeMinutes: z.number().int().positive().default(240),
      onStale: z.enum(['hedge_price', 'refuse']).default('hedge_price')
    })
  }),

  policy: StorePolicySchema,
  closes: z.array(CloseActionSchema).min(1),
  channels: z.array(ChannelConfigSchema).min(1),

  limits: z.object({
    conversationsPerMonth: z.number().int().positive().default(500),
    tokenBudgetPerSession: z.number().int().positive().default(40000),
    monthlySpendCapEur: z.number().nonnegative().default(25)
  }),

  compliance: z.object({
    aiDisclosure: z.literal(true, {
      errorMap: () => ({ message: 'aiDisclosure is required by EU AI Act Art. 50 and cannot be false.' })
    }),
    retentionDays: z.number().int().positive().default(30),
    dpaAcceptedAt: z.string().datetime().optional(),
    termsAcceptedAt: z.string().datetime().optional(),
    liabilityCapEur: z.number().positive().default(500).optional(),
    liabilityShieldAcknowledged: z.boolean().default(true).optional()
  })
});
export type TenantConfig = z.infer<typeof TenantConfigSchema>;
