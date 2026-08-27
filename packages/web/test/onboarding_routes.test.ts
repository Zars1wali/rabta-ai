import { describe, it, expect, vi } from 'vitest';
import {
  handleOnboardingVerifyRoute,
  handleOnboardingProvisionRoute
} from '../src/server/index.js';
import type { OnboardingService } from '@salesops/core';

describe('Onboarding API Routes (WP-17)', () => {
  const mockOnboardingService = {
    verifySource: vi.fn().mockResolvedValue({
      ok: true,
      itemCount: 5,
      sample: [{ sku: 'PROD-01', name: 'Item Teste', priceMinor: 1000, currency: 'EUR', available: true }],
      warnings: []
    }),
    provisionTenant: vi.fn().mockResolvedValue({
      ok: true,
      tenantId: '00000000-0000-4000-8000-000000000055',
      slug: 'loja-nova',
      embedSnippet: '<script src="https://agent.rewilt.com/widget.js" data-tenant-id="00000000-0000-4000-8000-000000000055" defer></script>',
      itemCount: 5
    })
  } as unknown as OnboardingService;

  it('verifies catalog source via POST /api/salesops/onboarding/verify', async () => {
    const req = new Request('http://localhost/api/salesops/onboarding/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sourceKind: 'csv',
        sourceConfig: { csvData: 'SKU,Name,Price\n1,2,3' }
      })
    });

    const res = await handleOnboardingVerifyRoute(req, { onboardingService: mockOnboardingService });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.ok).toBe(true);
    expect(data.itemCount).toBe(5);
  });

  it('provisions tenant via POST /api/salesops/onboarding/provision', async () => {
    const req = new Request('http://localhost/api/salesops/onboarding/provision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        slug: 'loja-nova',
        displayName: 'Loja Nova',
        sourceKind: 'csv',
        sourceConfig: {}
      })
    });

    const res = await handleOnboardingProvisionRoute(req, { onboardingService: mockOnboardingService });
    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.ok).toBe(true);
    expect(data.slug).toBe('loja-nova');
    expect(data.embedSnippet).toContain('data-tenant-id="00000000-0000-4000-8000-000000000055"');
  });
});
