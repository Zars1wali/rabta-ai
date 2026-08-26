import type { StalenessEvaluation } from './types.js';

export function evaluateStaleness(
  fetchedAtInput: Date | string,
  maxAgeMinutes: number = 240,
  onStale: 'hedge_price' | 'refuse' = 'hedge_price',
  now: Date = new Date()
): StalenessEvaluation {
  const fetchedAt = typeof fetchedAtInput === 'string' ? new Date(fetchedAtInput) : fetchedAtInput;
  const ageMs = now.getTime() - fetchedAt.getTime();
  const ageMinutes = Math.max(0, Math.floor(ageMs / (1000 * 60)));

  const isStale = ageMinutes > maxAgeMinutes;

  if (!isStale) {
    return {
      state: 'fresh',
      ageMinutes,
      maxAgeMinutes,
      action: 'none',
      disclaimer: null
    };
  }

  const disclaimer =
    onStale === 'hedge_price'
      ? 'A informação de preços ou stock pode requerer confirmação final no checkout.'
      : 'O catálogo está temporariamente indisponível para cotação em tempo real.';

  return {
    state: 'stale',
    ageMinutes,
    maxAgeMinutes,
    action: onStale,
    disclaimer
  };
}

export function formatHedgedPriceStatement(priceMinor: number, currency: string, locale = 'pt-PT'): string {
  const formattedPrice = (priceMinor / 100).toLocaleString(locale, {
    style: 'currency',
    currency
  });

  if (locale.startsWith('pt')) {
    return `estava a ${formattedPrice} na última verificação — a loja confirmará o valor exato no checkout`;
  }
  if (locale.startsWith('es')) {
    return `estaba a ${formattedPrice} en la última comprobación — la tienda confirmará el valor exacto en el checkout`;
  }
  return `was ${formattedPrice} when last checked — the store will confirm the exact price at checkout`;
}
