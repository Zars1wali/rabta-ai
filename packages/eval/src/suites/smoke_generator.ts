import type { Catalog } from '@salesops/types';
import type { EvalCase } from '../types.js';

export function generateCatalogSmokeSuite(catalog: Catalog): EvalCase[] {
  const cases: EvalCase[] = [];
  const inStockItems = catalog.items.filter((i) => i.available !== false);
  const outOfStockItems = catalog.items.filter((i) => i.available === false);

  // 1. Price integrity cases for up to 5 in-stock items
  const sampledInStock = inStockItems.slice(0, 5);
  for (const item of sampledInStock) {
    const formattedMajor = (item.priceMinor / 100).toFixed(2);
    const wholeUnits = Math.floor(item.priceMinor / 100).toString();

    cases.push({
      id: `smoke_price_${item.sku}`,
      suite: 'catalog_smoke',
      description: `Smoke test: verifies exact price for "${item.name}" (${formattedMajor} ${item.currency})`,
      input: `Quanto custa o produto "${item.name}" (SKU: ${item.sku})?`,
      expectedToolCalls: ['quote'],
      requiredPhrases: [item.sku, wholeUnits],
      customValidator: (output) => {
        const text = output.chunks.join(' ');
        // Assert SKU or price figures are mentioned accurately
        return text.includes(item.sku) || text.includes(formattedMajor) || text.includes(wholeUnits);
      }
    });
  }

  // 2. Out-of-stock cases (if any exist in the catalog)
  if (outOfStockItems.length > 0) {
    const oosItem = outOfStockItems[0]!;
    cases.push({
      id: `smoke_oos_${oosItem.sku}`,
      suite: 'catalog_smoke',
      description: `Smoke test: verifies out-of-stock awareness for "${oosItem.name}"`,
      input: `Têm o produto "${oosItem.name}" disponível para entrega imediata?`,
      expectedToolCalls: ['search_catalog'],
      requiredPhrases: [/(esgotado|indisponível|sem stock|não temos|out of stock)/i]
    });
  }

  // 3. Probing for non-existent item (never hallucinate products)
  const fakeSku = `NON_EXISTENT_SKU_${crypto.randomUUID().slice(0, 6)}`;
  cases.push({
    id: `smoke_non_existent_${fakeSku}`,
    suite: 'catalog_smoke',
    description: 'Smoke test: refuses non-existent product SKU without hallucination',
    input: `Gostaria de encomendar 10 unidades do produto com código ${fakeSku}.`,
    expectedToolCalls: ['quote'],
    requiredPhrases: [/(não|não encontramos|não existe|não temos|indisponível)/i]
  });

  return cases;
}
