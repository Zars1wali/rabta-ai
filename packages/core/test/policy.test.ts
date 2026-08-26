import { describe, it, expect } from 'vitest';
import { renderSystemPolicy } from '../src/agent/policy.js';
import { REWILT_TENANT_CONFIG } from '../src/db/seed.js';

describe('System Policy Renderer', () => {
  it('renders system policy with EU AI Act Art. 50 disclosure instructions', () => {
    const rendered = renderSystemPolicy({
      tenantName: 'Rewilt Sales Ops',
      stage: 'greet',
      allowedTransitions: ['discover', 'qualify'],
      localeHint: 'pt-PT',
      persona: REWILT_TENANT_CONFIG.persona,
      storePolicy: REWILT_TENANT_CONFIG.policy
    });

    expect(rendered).toContain('EU AI ACT ART. 50 MANDATE');
    expect(rendered).toContain('Your first message in any conversation must state plainly and naturally that the user is interacting with an AI sales assistant');
    expect(rendered).toContain('Rewilt Sales Ops');
  });

  it('guarantees that the product catalog is NOT injected in the prompt', () => {
    const rendered = renderSystemPolicy({
      tenantName: 'Rewilt Sales Ops',
      stage: 'greet',
      allowedTransitions: ['discover'],
      localeHint: 'pt-PT'
    });

    expect(rendered).toContain('The product catalog is NOT in this prompt');
    expect(rendered).toContain('NEVER invent, estimate, or assume a price');
    // Ensure catalog SKU strings do NOT appear in the rendered system policy
    expect(rendered).not.toContain('salesops_lite');
    expect(rendered).not.toContain('salesops_premium');
  });

  it('places dynamic state at the very end of the prompt for cache optimization', () => {
    const rendered = renderSystemPolicy({
      tenantName: 'Rewilt Sales Ops',
      stage: 'objection',
      allowedTransitions: ['close', 'handoff'],
      localeHint: 'es-ES'
    });

    const lines = rendered.trim().split('\n');
    const lastBlock = lines.slice(-4).join('\n');

    expect(lastBlock).toContain('Active funnel stage: objection');
    expect(lastBlock).toContain('Permitted stage transitions: [close, handoff]');
    expect(lastBlock).toContain('Language / locale hint: es-ES');
  });
});
