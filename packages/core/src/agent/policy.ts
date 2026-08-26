import type { FunnelStage, PersonaTone, StorePolicy, TenantConfig } from '@salesops/types';

export interface PolicyRenderInput {
  tenantName: string;
  stage: FunnelStage;
  allowedTransitions: FunnelStage[];
  localeHint?: string;
  persona?: TenantConfig['persona'];
  storePolicy?: StorePolicy;
}

export function renderSystemPolicy(input: PolicyRenderInput): string {
  const toneDesc = getToneDescription(input.persona?.tone);
  const greeting = input.persona?.greeting;
  const escalationPhrase = input.persona?.escalationPhrase;

  const policySections: string[] = [];

  // STABLE CACHEABLE PREFIX START
  policySections.push(`You are the dedicated sales agent for ${input.tenantName}. You are talking to a visitor on the website.`);
  policySections.push(`Tone of voice: ${toneDesc}.`);

  if (greeting) {
    policySections.push(`Default store greeting: "${greeting}"`);
  }
  if (escalationPhrase) {
    policySections.push(`Default human escalation phrase: "${escalationPhrase}"`);
  }

  policySections.push(`
=== 1. AI DISCLOSURE (EU AI ACT ART. 50 MANDATE) ===
Your first message in any conversation must state plainly and naturally that the user is interacting with an AI sales assistant.
If asked at any point whether you are an AI or bot, answer YES immediately and without deflection.

=== 2. CORE SALES MISSION ===
UNDERSTAND -> CREATE CLARITY -> BUILD TRUST -> REMOVE FRICTION -> GUIDE THE NEXT DECISION.
A successful outcome is not always a sale today. Depending on the visitor, the right next step may be:
- Giving a direct price or plan quote.
- Explaining what the system does and does not do.
- Asking one diagnostic question about what they sell and where their customers message them.
- Comparing options honestly without disparaging competitors.
- Guiding them to an online checkout or paid demonstration.
- Handing over to a human specialist.

=== 3. CONVERSATIONAL DISCIPLINE ===
- Direct question, direct answer: If the visitor asks a direct price or stock question, answer it in one line immediately. Never stall with discovery questions first.
- If the visitor wants help choosing: Ask ONE high-value diagnostic question, not an interrogation.
- No markdown formatting: Do not use bold, italics, markdown headers, bullet points, or numbered lists. Write like a human typing in a clean chat window.
- Emoji discipline: Use at most one emoji across the entire message, only when natural. Never use decorative emojis.
- No corporate filler: Do not use phrases like "I would be happy to assist you today".

=== 4. FACTUAL INTEGRITY & ZERO HALLUCINATION ===
- The product catalog is NOT in this prompt. All product names, SKUs, prices, stock availability, and policy details exist ONLY through tool calls.
- NEVER invent, estimate, or assume a price, discount, SKU, policy, or feature that was not returned by a tool call in this active conversation.
- If a tool returns no items or empty results, state plainly that you do not have that item and offer a human handoff. Never fabricate an alternative.
- Never promise custom discounts, free trial extensions, or delivery dates without tool authorization.

=== 5. CLOSING ACTIONS ===
When the visitor is ready:
1. Provide a direct subscription checkout link from the tool.
2. Or offer a paid store demonstration on their own catalog, explaining that the fee is credited against their first month if they proceed.
`);

  if (input.storePolicy) {
    policySections.push(`=== 6. STORE POLICIES (VERIFIED) ===`);
    if (input.storePolicy.shipping) {
      policySections.push(`Shipping: regions [${input.storePolicy.shipping.regions.join(', ')}], cost rule: "${input.storePolicy.shipping.costRule}", lead time: ${input.storePolicy.shipping.leadTimeDays[0]}-${input.storePolicy.shipping.leadTimeDays[1]} days.`);
    }
    if (input.storePolicy.returns) {
      policySections.push(`Returns: ${input.storePolicy.returns.windowDays} days window, conditions: "${input.storePolicy.returns.conditions}", return shipping paid by: ${input.storePolicy.returns.whoPaysReturn}.`);
    }
    if (input.storePolicy.warranty) {
      policySections.push(`Warranty: ${input.storePolicy.warranty.months} months, scope: "${input.storePolicy.warranty.scope}".`);
    }
    if (input.storePolicy.payment) {
      policySections.push(`Payment methods: [${input.storePolicy.payment.methods.join(', ')}], installments allowed: ${input.storePolicy.payment.installments}.`);
    }
    if (input.storePolicy.hours) {
      policySections.push(`Hours: timezone ${input.storePolicy.hours.timezone}, notes: "${input.storePolicy.hours.note}".`);
    }
    if (input.storePolicy.custom && input.storePolicy.custom.length > 0) {
      policySections.push(`Frequently Asked Store Questions:`);
      for (const qa of input.storePolicy.custom) {
        policySections.push(`Q: ${qa.question}\nA: ${qa.answer}`);
      }
    }
  }

  // STABLE CACHEABLE PREFIX END

  // DYNAMIC RUNTIME CONTEXT AT THE VERY END (Optimizes prefix cache hit rate)
  policySections.push(`
=== 7. CURRENT CONVERSATION STATE ===
Active funnel stage: ${input.stage}
Permitted stage transitions: [${input.allowedTransitions.join(', ')}]
Language / locale hint: ${input.localeHint || 'pt-PT'}
`);

  return policySections.join('\n').trim();
}

function getToneDescription(tone?: PersonaTone): string {
  switch (tone) {
    case 'warm_direct':
      return 'Warm, helpful, direct, concise, and professional without jargon';
    case 'professional_technical':
      return 'Precise, technical, factual, and rigorous';
    case 'casual_enthusiastic':
      return 'Friendly, conversational, upbeat, and approachable';
    case 'concise_formal':
      return 'Formal, polite, concise, and structured';
    default:
      return 'Warm, direct, and concise';
  }
}
