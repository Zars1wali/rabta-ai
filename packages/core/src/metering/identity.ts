import crypto from 'crypto';

export function computeIdentityHash(
  secret: string,
  channel: string,
  visitorIdentifier: string
): string {
  const normalized = `${channel.toLowerCase()}:${visitorIdentifier.trim()}`;
  return crypto.createHmac('sha256', secret).update(normalized).digest('hex');
}

export function computeWindowBounds(now: Date = new Date()): { windowStart: Date; windowEnd: Date } {
  const windowStart = new Date(now);
  const windowEnd = new Date(now.getTime() + 24 * 60 * 60 * 1000); // 24 hours
  return { windowStart, windowEnd };
}

export function computeWindowId(
  tenantId: string,
  channel: string,
  identityHash: string,
  windowStart: Date
): string {
  const isoHour = windowStart.toISOString().slice(0, 13); // "YYYY-MM-DDTHH"
  return `${tenantId}:${channel}:${identityHash.slice(0, 16)}:${isoHour}`;
}
