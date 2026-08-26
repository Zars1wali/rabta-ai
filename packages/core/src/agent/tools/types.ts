import { z } from 'zod';
import type { ToolDeclaration } from '../../llm/types.js';
import type { AgentEvent } from '@salesops/types';
import type { CatalogService } from '../../catalog/service.js';
import type {
  SessionRepository,
  LeadRepository,
  TenantRepository,
  ToolCallRepository
} from '../../db/repositories.js';

export interface ToolExecutionContext {
  tenantId: string;
  sessionId: string;
  catalogService: CatalogService;
  sessionRepo: SessionRepository;
  leadRepo: LeadRepository;
  tenantRepo: TenantRepository;
  toolCallRepo: ToolCallRepository;
  stripeCheckoutCreator?: (params: {
    tenantId: string;
    sessionId: string;
    sku: string;
    email?: string;
    locale: string;
    mode: 'subscription' | 'payment';
    priceMinor?: number;
  }) => Promise<string>;
}

export interface ToolExecutionOutput {
  result: Record<string, unknown>;
  ok: boolean;
  event?: AgentEvent;
}

export interface AgentTool<TSchema extends z.ZodTypeAny = z.ZodTypeAny> {
  readonly name: string;
  readonly description: string;
  readonly schema: TSchema;
  readonly declaration: ToolDeclaration;
  execute(args: z.infer<TSchema>, context: ToolExecutionContext): Promise<ToolExecutionOutput>;
}
