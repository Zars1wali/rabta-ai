import { z } from 'zod';

export const LeadFieldSchema = z.enum(['name', 'email', 'phone', 'company_url', 'notes']);
export type LeadField = z.infer<typeof LeadFieldSchema>;

export const NotifyTargetSchema = z.object({
  type: z.enum(['whatsapp', 'email', 'webhook']),
  to: z.string().min(1)
});
export type NotifyTarget = z.infer<typeof NotifyTargetSchema>;

export const CloseActionProductLinkSchema = z.object({
  kind: z.literal('product_link'),
  urlTemplate: z.string().min(1)
});

export const CloseActionAddToCartSchema = z.object({
  kind: z.literal('add_to_cart'),
  endpoint: z.string().url()
});

export const CloseActionCaptureLeadSchema = z.object({
  kind: z.literal('capture_lead'),
  fields: z.array(LeadFieldSchema).min(1),
  notify: NotifyTargetSchema
});

export const CloseActionBookSlotSchema = z.object({
  kind: z.literal('book_slot'),
  provider: z.enum(['cal', 'google']),
  calendarId: z.string().min(1)
});

export const CloseActionStripeCheckoutSchema = z.object({
  kind: z.literal('stripe_checkout'),
  priceMap: z.record(z.string())
});

export const CloseActionHandoffSchema = z.object({
  kind: z.literal('handoff'),
  target: NotifyTargetSchema
});

export const CloseActionSchema = z.discriminatedUnion('kind', [
  CloseActionProductLinkSchema,
  CloseActionAddToCartSchema,
  CloseActionCaptureLeadSchema,
  CloseActionBookSlotSchema,
  CloseActionStripeCheckoutSchema,
  CloseActionHandoffSchema
]);
export type CloseAction = z.infer<typeof CloseActionSchema>;
