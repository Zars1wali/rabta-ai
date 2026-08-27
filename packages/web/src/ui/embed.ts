'use client';

import React from 'react';
import { createRoot } from 'react-dom/client';
import { SalesOpsWidget, type SalesOpsWidgetProps } from './Widget.js';

declare global {
  interface Window {
    initSalesOpsWidget?: (config?: SalesOpsWidgetProps) => void;
  }
}

export function initSalesOpsWidget(config: SalesOpsWidgetProps = {}) {
  if (typeof document === 'undefined') return;

  const existingRoot = document.getElementById('salesops-widget-container');
  if (existingRoot) return;

  const container = document.createElement('div');
  container.id = 'salesops-widget-container';
  document.body.appendChild(container);

  const root = createRoot(container);
  root.render(React.createElement(SalesOpsWidget, config));
}

if (typeof window !== 'undefined') {
  window.initSalesOpsWidget = initSalesOpsWidget;
}
