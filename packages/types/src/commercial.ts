import { z } from 'zod';

// 1. Lead State & Type Schemas
export const LeadStateSchema = z.enum([
  'new',
  'qualifying',
  'interested',
  'quoted',
  'order_pending',
  'won',
  'lost',
  'dormant'
]);
export type LeadState = z.infer<typeof LeadStateSchema>;

export const LeadTypeSchema = z.enum([
  'quote_request',
  'appointment_request',
  'product_enquiry',
  'emergency'
]);
export type LeadType = z.infer<typeof LeadTypeSchema>;

// 2. Channel & Contact Schemas
export const ChannelTypeSchema = z.enum(['whatsapp', 'web_widget', 'instagram', 'email']);
export type ChannelType = z.infer<typeof ChannelTypeSchema>;

export const ContactSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  waId: z.string().nullable().optional(),
  displayName: z.string().nullable().optional(),
  phoneE164: z.string().nullable().optional(),
  language: z.string().default('de'),
  tags: z.array(z.string()).default([]),
  consentSource: z.string().nullable().optional(),
  consentAt: z.string().datetime().nullable().optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});
export type Contact = z.infer<typeof ContactSchema>;

// 3. Conversation & Message Schemas
export const ConversationStatusSchema = z.enum(['open', 'snoozed', 'closed']);
export type ConversationStatus = z.infer<typeof ConversationStatusSchema>;

export const AiModeSchema = z.enum(['off', 'suggest', 'auto']);
export type AiMode = z.infer<typeof AiModeSchema>;

export const ConversationSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  channelId: z.string().uuid(),
  contactId: z.string().uuid(),
  status: ConversationStatusSchema.default('open'),
  serviceWindowExpiresAt: z.string().datetime().nullable().optional(),
  aiMode: AiModeSchema.default('suggest'),
  lastMessageAt: z.string().datetime(),
  createdAt: z.string().datetime()
});
export type Conversation = z.infer<typeof ConversationSchema>;

export const MessageDirectionSchema = z.enum(['inbound', 'outbound']);
export type MessageDirection = z.infer<typeof MessageDirectionSchema>;

export const MessageTypeSchema = z.enum(['text', 'audio', 'image', 'document', 'interactive']);
export type MessageType = z.infer<typeof MessageTypeSchema>;

export const MessageBillingCategorySchema = z.enum([
  'service',
  'utility',
  'marketing',
  'authentication',
  'free_tier'
]);
export type MessageBillingCategory = z.infer<typeof MessageBillingCategorySchema>;

export const CommercialMessageSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  conversationId: z.string().uuid(),
  direction: MessageDirectionSchema,
  wamid: z.string().nullable().optional(), // WhatsApp message ID for strict idempotency
  type: MessageTypeSchema.default('text'),
  body: z.string().nullable().optional(),
  mediaUrl: z.string().url().nullable().optional(),
  billingCategory: MessageBillingCategorySchema.default('service'),
  costEstimateMinor: z.number().int().default(0),
  author: z.string().default('agent'), // 'customer' | 'agent' | 'human_agent' | 'system'
  rawPayload: z.record(z.unknown()).nullable().optional(),
  createdAt: z.string().datetime()
});
export type CommercialMessage = z.infer<typeof CommercialMessageSchema>;

// 4. Offerings & Catalog
export const PriceTypeSchema = z.enum(['fixed', 'hourly', 'estimate', 'tiered']);
export type PriceType = z.infer<typeof PriceTypeSchema>;

export const OfferingSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  sku: z.string().min(1),
  name: z.string().min(1),
  description: z.string().nullable().optional(),
  priceType: PriceTypeSchema.default('fixed'),
  priceMinor: z.number().int(),
  currency: z.string().default('CHF'),
  serviceArea: z.string().nullable().optional(),
  durationMinutes: z.number().int().nullable().optional(),
  active: z.boolean().default(true),
  attributes: z.record(z.unknown()).default({}),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});
export type Offering = z.infer<typeof OfferingSchema>;

// 5. Quote Request & Structured Fields
export const QuoteRequestFieldsSchema = z.object({
  propertyType: z.string().optional(),
  rooms: z.number().optional(),
  squareMeters: z.number().optional(),
  frequency: z.string().optional(),
  location: z.string().optional(),
  postalCode: z.string().optional(),
  targetDate: z.string().optional(),
  handoverGuarantee: z.boolean().optional(),
  specialRequirements: z.array(z.string()).optional()
});
export type QuoteRequestFields = z.infer<typeof QuoteRequestFieldsSchema>;

export const QuoteRequestSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  leadId: z.string().uuid(),
  fields: QuoteRequestFieldsSchema.default({}),
  completeness: z.number().min(0).max(1).default(0), // 0.0 to 1.0
  missingFields: z.array(z.string()).default([]),
  suggestedPackage: z.string().nullable().optional(),
  createdAt: z.string().datetime()
});
export type QuoteRequest = z.infer<typeof QuoteRequestSchema>;

// 6. Lead Entity (Commercial)
export const CommercialLeadSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  contactId: z.string().uuid(),
  conversationId: z.string().uuid().nullable().optional(),
  leadType: LeadTypeSchema.default('quote_request'),
  state: LeadStateSchema.default('new'),
  score: z.number().int().min(0).max(100).default(50),
  valueEstimateMinor: z.number().int().default(0),
  currency: z.string().default('CHF'),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});
export type CommercialLead = z.infer<typeof CommercialLeadSchema>;

// 7. Orders & Payments
export const OrderStatusSchema = z.enum(['draft', 'pending', 'paid', 'cancelled']);
export type OrderStatus = z.infer<typeof OrderStatusSchema>;

export const OrderLineItemSchema = z.object({
  sku: z.string(),
  name: z.string(),
  quantity: z.number().int().positive(),
  unitPriceMinor: z.number().int(),
  totalPriceMinor: z.number().int()
});
export type OrderLineItem = z.infer<typeof OrderLineItemSchema>;

export const OrderSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  leadId: z.string().uuid(),
  contactId: z.string().uuid(),
  lineItems: z.array(OrderLineItemSchema).default([]),
  status: OrderStatusSchema.default('draft'),
  amountMinor: z.number().int().default(0),
  currency: z.string().default('CHF'),
  stripePaymentIntentId: z.string().nullable().optional(),
  stripeCheckoutId: z.string().nullable().optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});
export type Order = z.infer<typeof OrderSchema>;

export const PaymentSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  orderId: z.string().uuid(),
  stripePaymentIntentId: z.string(),
  amountMinor: z.number().int(),
  currency: z.string().default('CHF'),
  status: z.enum(['succeeded', 'refunded', 'failed']).default('succeeded'),
  createdAt: z.string().datetime()
});
export type Payment = z.infer<typeof PaymentSchema>;

// 8. Append-Only Timeline Event
export const TimelineEventSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  aggregateType: z.enum(['lead', 'conversation', 'order', 'contact']),
  aggregateId: z.string().uuid(),
  eventType: z.string().min(1),
  payload: z.record(z.unknown()).default({}),
  createdAt: z.string().datetime()
});
export type TimelineEvent = z.infer<typeof TimelineEventSchema>;

// 9. AI Run Tracking
export const AiRunOutcomeSchema = z.enum(['auto_sent', 'drafted', 'escalated', 'refused']);
export type AiRunOutcome = z.infer<typeof AiRunOutcomeSchema>;

export const AiRunSchema = z.object({
  id: z.string().uuid(),
  tenantId: z.string().uuid(),
  conversationId: z.string().uuid(),
  messageId: z.string().uuid().nullable().optional(),
  model: z.string(),
  inputTokens: z.number().int().default(0),
  outputTokens: z.number().int().default(0),
  latencyMs: z.number().int().default(0),
  promptRef: z.string().nullable().optional(),
  outcome: AiRunOutcomeSchema.default('drafted'),
  createdAt: z.string().datetime()
});
export type AiRun = z.infer<typeof AiRunSchema>;
