import { describe, it, expect, vi } from 'vitest';
import { DigestService, type WeeklyDigestMetrics } from '../src/reporting/index.js';
import type { NotificationDispatcher } from '../src/notifications/types.js';
import { REWILT_TENANT_ID } from '../src/db/seed.js';

describe('Automated Weekly Performance Digest (WP-29)', () => {
  const tenantId = REWILT_TENANT_ID;
  const digestService = new DigestService();

  const sampleMetrics: WeeklyDigestMetrics = {
    tenantId,
    periodStart: '2026-08-20',
    periodEnd: '2026-08-27',
    conversationsServed: 142,
    leadsCaptured: 18,
    checkoutsCreated: 6,
    revenueMinor: 47400, // 474.00 €
    topSkus: [
      { sku: 'salesops_std', name: 'Sales Ops Standard', count: 68 },
      { sku: 'salesops_eu', name: 'Sales Ops Europe', count: 42 },
      { sku: 'salesops_prem', name: 'Sales Ops Premium', count: 15 }
    ],
    objectionsHandled: 24,
    tokensUsed: 485000,
    planUtilizationPercent: 71,
    recommendation: {
      type: 'maintain',
      headline: 'O seu plano atual está calibrado e otimizado',
      explanation: 'Utilizou 71% da capacidade do plano. Projeção estável.',
      breakdown: {
        optionA: { name: 'Sales Ops Standard', costEur: 79, details: '500 convs' },
        recommendedOption: 'Sales Ops Standard'
      }
    }
  };

  it('formats weekly performance digest in structured Markdown', () => {
    const md = digestService.formatDigestMarkdown(sampleMetrics, 'Rewilt');

    expect(md).toContain('# 📊 Relatório Semanal de Desempenho — Rewilt');
    expect(md).toContain('142'); // Conversations
    expect(md).toContain('18');  // Leads
    expect(md).toContain('474.00 €'); // Revenue
    expect(md).toContain('**Sales Ops Standard** (salesops_std) — 68 consultas');
    expect(md).toContain('71%'); // Utilization
    expect(md).toContain('O seu plano atual está calibrado e otimizado');
  });

  it('dispatches weekly digest email via NotificationDispatcher', async () => {
    const mockDispatcher: NotificationDispatcher = {
      dispatch: vi.fn().mockResolvedValue({
        sent: true,
        channel: 'email',
        target: 'loja@rewilt.com'
      })
    };

    const res = await digestService.dispatchWeeklyDigest(
      sampleMetrics,
      mockDispatcher,
      'loja@rewilt.com',
      'Rewilt'
    );

    expect(res.sent).toBe(true);
    expect(mockDispatcher.dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'handoff_requested',
        tenantId,
        target: { type: 'email', to: 'loja@rewilt.com' }
      })
    );
  });
});
