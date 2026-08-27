import {
  AgentTurnExecutor,
  CatalogService,
  MockLlmProviderAdapter,
  ZPI_TENANT_ID,
  ZPI_TENANT_CONFIG,
  ZPI_CATALOG,
  type SessionRepository,
  type MessageRepository,
  type ToolCallRepository,
  type CatalogRepository,
  type TenantRepository,
  type ToolDeclaration
} from '@salesops/core';
import type { AgentTurnInput } from '@salesops/types';

const mockCatalogRepo = {
  getActiveSnapshot: async () => ({
    snapshot: {
      id: 'snap-zpi-1',
      tenantId: ZPI_TENANT_ID,
      sourceKind: 'json',
      fetchedAt: new Date(),
      itemCount: ZPI_CATALOG.items.length,
      status: 'active',
      createdAt: new Date()
    },
    items: ZPI_CATALOG.items
  }),
  searchItems: async (_tId: string, options: { query?: string }) => {
    if (!options.query) return ZPI_CATALOG.items;
    const q = options.query.toLowerCase();
    return ZPI_CATALOG.items.filter(
      (i) => i.name.toLowerCase().includes(q) || (i.description ? i.description.toLowerCase().includes(q) : false)
    );
  },
  getItemBySku: async (_tId: string, sku: string) => {
    return ZPI_CATALOG.items.find((i) => i.sku === sku) ?? null;
  }
} as unknown as CatalogRepository;

const mockTenantRepo = {
  getById: async (id: string) => {
    if (id === ZPI_TENANT_ID) {
      return {
        id: ZPI_TENANT_ID,
        slug: 'zpi',
        displayName: ZPI_TENANT_CONFIG.displayName,
        config: ZPI_TENANT_CONFIG
      };
    }
    return null;
  }
} as unknown as TenantRepository;

const catalogService = new CatalogService(mockCatalogRepo, mockTenantRepo);

const mockSessionRepo = {
  getSession: async () => ({
    id: 'session-zpi-1',
    tenantId: ZPI_TENANT_ID,
    tokensUsed: 0
  }),
  updateTurn: async () => ({ id: 'session-zpi-1' })
} as unknown as SessionRepository;

const mockMessageRepo = {
  getRecentHistory: async () => [],
  addMessage: async () => ({ id: 'msg-zpi-1' })
} as unknown as MessageRepository;

const mockToolCallRepo = {
  recordToolCall: async () => ({ id: 'call-zpi-1' })
} as unknown as ToolCallRepository;

const mockLlm = new MockLlmProviderAdapter(async (messages) => {
  const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')?.content.toLowerCase() || '';
  const lastTool = [...messages].reverse().find((m) => m.role === 'tool');

  if (lastTool) {
    let resultObj: Record<string, unknown> = {};
    try {
      resultObj = JSON.parse(lastTool.content);
    } catch {
      resultObj = {};
    }

    if (resultObj.item || resultObj.items) {
      return {
        text: 'The comprehensive EU AI Act Article 50 & 52 audit is priced at €1,500.00 with a 48h turnaround time. The ZeroPoint SOC is €490.00/month.',
        toolCalls: [],
        finishReason: 'STOP',
        usage: { inputTokens: 40, outputTokens: 30 }
      };
    }
  }

  if (lastUserMsg.includes('price') || lastUserMsg.includes('cost') || lastUserMsg.includes('audit') || lastUserMsg.includes('quote')) {
    return {
      text: '',
      toolCalls: [{ id: 'call_quote_1', name: 'quote', arguments: { skus: ['zpi_ai_act_audit'] } }],
      finishReason: 'TOOL_CALL',
      usage: { inputTokens: 35, outputTokens: 20 }
    };
  }

  return {
    text: 'ZeroPointIntel provides certified EU AI Act Article 50 & 52 conformity audits, continuous red-teaming, and runtime prompt injection firewalls. How can our security team assist your deployment?',
    toolCalls: [],
    finishReason: 'STOP',
    usage: { inputTokens: 45, outputTokens: 35 }
  };
});

const defaultTools: ToolDeclaration[] = [
  {
    name: 'quote',
    description: 'Get verified quote for SKUs',
    parameters: { type: 'object', properties: { skus: { type: 'array' } } }
  },
  {
    name: 'search_catalog',
    description: 'Search security services',
    parameters: { type: 'object', properties: { query: { type: 'string' } } }
  }
];

const executor = new AgentTurnExecutor({
  llm: mockLlm,
  sessionRepo: mockSessionRepo,
  messageRepo: mockMessageRepo,
  tenantRepo: mockTenantRepo,
  toolCallRepo: mockToolCallRepo,
  tools: defaultTools,
  toolHandler: async (tc) => {
    if (tc.name === 'quote') {
      const quoteRes = await catalogService.getBySku(ZPI_TENANT_ID, 'zpi_ai_act_audit');
      const item = quoteRes.item;
      return {
        ok: true,
        latencyMs: 12,
        result: {
          items: item ? [item] : [],
          totalMinor: item ? item.priceMinor : 0,
          currency: 'EUR'
        }
      };
    }
    const results = await catalogService.search(ZPI_TENANT_ID, { query: '' });
    return {
      ok: true,
      latencyMs: 15,
      result: { items: results.items }
    };
  }
});

export async function POST(req: Request) {
  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ ok: false, error: 'Invalid JSON body' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const sessionId = body.sessionId || crypto.randomUUID();
  const content = body.message?.content || '';
  const locale = body.locale || 'en';

  const turnInput: AgentTurnInput = {
    sessionId,
    tenantId: ZPI_TENANT_ID,
    message: {
      id: crypto.randomUUID(),
      channel: 'web',
      sessionId,
      senderId: 'visitor',
      content,
      mediaUrl: null,
      timestamp: new Date().toISOString()
    },
    history: [],
    stage: 'discover',
    locale
  };

  const output = await executor.executeTurn(turnInput);

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of output.chunks) {
        const words = chunk.split(' ');
        for (let i = 0; i < words.length; i++) {
          const wordWithSpace = i === words.length - 1 ? words[i]! : `${words[i]} `;
          const sseToken = `event: token\ndata: ${JSON.stringify({ text: wordWithSpace })}\n\n`;
          controller.enqueue(encoder.encode(sseToken));
        }
      }

      for (const event of output.events) {
        const sseEvent = `event: event\ndata: ${JSON.stringify(event)}\n\n`;
        controller.enqueue(encoder.encode(sseEvent));
      }

      const sseDone = `event: done\ndata: ${JSON.stringify({
        stage: output.stage,
        toolCalls: output.toolCalls,
        usage: output.usage
      })}\n\n`;
      controller.enqueue(encoder.encode(sseDone));

      controller.close();
    }
  });

  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive'
    }
  });
}
