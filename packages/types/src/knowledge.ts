import { z } from 'zod';

export const CustomQAPairSchema = z.object({
  question: z.string().min(1, 'Question must not be empty'),
  answer: z.string().min(1, 'Answer must not be empty')
});
export type CustomQAPair = z.infer<typeof CustomQAPairSchema>;

export const StorePolicySchema = z.object({
  shipping: z
    .object({
      regions: z.array(z.string()),
      costRule: z.string(),
      leadTimeDays: z.tuple([z.number().int().nonnegative(), z.number().int().nonnegative()])
    })
    .nullable(),
  returns: z
    .object({
      windowDays: z.number().int().nonnegative(),
      conditions: z.string(),
      whoPaysReturn: z.enum(['customer', 'store'])
    })
    .nullable(),
  warranty: z
    .object({
      months: z.number().int().nonnegative(),
      scope: z.string()
    })
    .nullable(),
  payment: z
    .object({
      methods: z.array(z.string()),
      installments: z.boolean()
    })
    .nullable(),
  hours: z
    .object({
      timezone: z.string(),
      note: z.string()
    })
    .nullable(),
  contact: z.object({
    humanEscalation: z.string().min(1)
  }),
  custom: z.array(CustomQAPairSchema).max(20, 'Maximum 20 custom QA pairs allowed').default([])
});
export type StorePolicy = z.infer<typeof StorePolicySchema>;
