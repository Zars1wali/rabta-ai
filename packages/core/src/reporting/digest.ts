import type { PlanRecommendation } from '../metering/forecast.js';
import type { NotificationDispatcher } from '../notifications/types.js';

export interface TopSkuSummary {
  sku: string;
  name: string;
  count: number;
}

export interface WeeklyDigestMetrics {
  tenantId: string;
  periodStart: string; // "YYYY-MM-DD"
  periodEnd: string;   // "YYYY-MM-DD"
  conversationsServed: number;
  leadsCaptured: number;
  checkoutsCreated: number;
  revenueMinor: number;
  topSkus: TopSkuSummary[];
  objectionsHandled: number;
  tokensUsed: number;
  planUtilizationPercent: number;
  recommendation?: PlanRecommendation;
}

export class DigestService {
  formatDigestMarkdown(metrics: WeeklyDigestMetrics, storeName = 'A sua Loja'): string {
    const formattedRevenue = (metrics.revenueMinor / 100).toFixed(2);
    const topSkusList =
      metrics.topSkus.length > 0
        ? metrics.topSkus.map((s, idx) => `${idx + 1}. **${s.name}** (${s.sku}) — ${s.count} consultas`).join('\n')
        : 'Nenhum produto consultado esta semana.';

    let md = `# 📊 Relatório Semanal de Desempenho — ${storeName}
**Período:** ${metrics.periodStart} a ${metrics.periodEnd}

---

### 📈 Métricas de Atendimento & Vendas
* 💬 **Conversações Atendidas:** ${metrics.conversationsServed}
* 🎯 **Leads Qualificadas Recolhidas:** ${metrics.leadsCaptured}
* 💳 **Checkouts / Vendas Geradas:** ${metrics.checkoutsCreated}
* 💰 **Volume Estimado de Vendas:** ${formattedRevenue} €
* 🛡️ **Objeções Resolvidas Factualmente:** ${metrics.objectionsHandled}

---

### 🏆 Top Produtos Mais Consultados
${topSkusList}

---

### ⚙️ Capacidade & Utilização do Plano
* **Tokens de IA Consumidos:** ${metrics.tokensUsed.toLocaleString()}
* **Utilização da Capacidade do Plano:** ${metrics.planUtilizationPercent}%
`;

    if (metrics.recommendation) {
      md += `
---

### 💡 Recomendação de Otimização do Plano
**${metrics.recommendation.headline}**
${metrics.recommendation.explanation}
`;
    }

    return md;
  }

  async dispatchWeeklyDigest(
    metrics: WeeklyDigestMetrics,
    dispatcher: NotificationDispatcher,
    emailTarget = 'comercial@rewilt.com',
    storeName = 'A sua Loja'
  ): Promise<{ sent: boolean }> {
    const markdownContent = this.formatDigestMarkdown(metrics, storeName);

    const res = await dispatcher.dispatch({
      type: 'handoff_requested',
      tenantId: metrics.tenantId,
      sessionId: `digest-${metrics.periodStart}`,
      reason: `Relatório Semanal SalesOps (${metrics.periodStart} a ${metrics.periodEnd}): ${metrics.conversationsServed} conversações, ${metrics.leadsCaptured} leads.`,
      target: { type: 'email', to: emailTarget },
      transcript: [{ role: 'agent', content: markdownContent }]
    });

    return { sent: res.sent };
  }
}
