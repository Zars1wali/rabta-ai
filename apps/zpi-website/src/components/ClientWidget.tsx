'use client';

import dynamic from 'next/dynamic';

const SalesOpsWidget = dynamic(
  () => import('@salesops/web/ui').then((mod) => mod.SalesOpsWidget),
  { ssr: false }
);

export function ClientWidget() {
  return (
    <SalesOpsWidget
      tenantId="00000000-0000-4000-8000-000000000002"
      apiBaseUrl="/api"
      storeName="ZeroPoint Security Copilot"
      primaryColor="#10b981"
      position="bottom-right"
      locale="en"
    />
  );
}
