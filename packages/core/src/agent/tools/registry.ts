import type { ToolDeclaration, LlmToolCall } from '../../llm/types.js';
import type { AgentTool, ToolExecutionContext, ToolExecutionOutput } from './types.js';
import { searchCatalogTool } from './search_catalog.js';
import { quoteTool } from './quote.js';
import { getPolicyTool } from './get_policy.js';
import { createSubscriptionCheckoutTool } from './create_subscription_checkout.js';
import { createPreviewCheckoutTool } from './create_preview_checkout.js';
import { captureLeadTool } from './capture_lead.js';
import { requestHumanTool } from './request_human.js';

export class ToolRegistry {
  private tools = new Map<string, AgentTool>();

  constructor() {
    this.register(searchCatalogTool);
    this.register(quoteTool);
    this.register(getPolicyTool);
    this.register(createSubscriptionCheckoutTool);
    this.register(createPreviewCheckoutTool);
    this.register(captureLeadTool);
    this.register(requestHumanTool);
  }

  register(tool: AgentTool) {
    this.tools.set(tool.name, tool);
  }

  getTool(name: string): AgentTool | undefined {
    return this.tools.get(name);
  }

  getDeclarations(): ToolDeclaration[] {
    return Array.from(this.tools.values()).map((t) => t.declaration);
  }

  async execute(toolCall: LlmToolCall, context: ToolExecutionContext): Promise<ToolExecutionOutput> {
    const tool = this.tools.get(toolCall.name);
    if (!tool) {
      return {
        ok: false,
        result: {
          error: `Tool "${toolCall.name}" is not recognized or available on the server.`
        }
      };
    }

    const parseResult = tool.schema.safeParse(toolCall.arguments);
    if (!parseResult.success) {
      return {
        ok: false,
        result: {
          error: `Invalid tool arguments for "${toolCall.name}": ${parseResult.error.message}`,
          validationIssues: parseResult.error.issues
        }
      };
    }

    try {
      return await tool.execute(parseResult.data, context);
    } catch (err: unknown) {
      return {
        ok: false,
        result: {
          error: `Tool execution failed: ${(err as Error).message}`
        }
      };
    }
  }
}

export const defaultToolRegistry = new ToolRegistry();
export const DEFAULT_TOOL_DECLARATIONS: ToolDeclaration[] = defaultToolRegistry.getDeclarations();
