import type { RateLimitCheckResult } from './types.js';

export class SlidingWindowRateLimiter {
  private windows = new Map<string, number[]>();

  isAllowed(
    identifier: string,
    limit: number = 30,
    windowSeconds: number = 60,
    now: number = Date.now()
  ): RateLimitCheckResult {
    const windowMs = windowSeconds * 1000;
    const threshold = now - windowMs;

    const timestamps = this.windows.get(identifier) || [];
    const validTimestamps = timestamps.filter((t) => t > threshold);

    if (validTimestamps.length >= limit) {
      const oldest = validTimestamps[0] || now;
      const resetMs = Math.max(0, oldest + windowMs - now);

      this.windows.set(identifier, validTimestamps);
      return {
        allowed: false,
        remaining: 0,
        resetMs
      };
    }

    validTimestamps.push(now);
    this.windows.set(identifier, validTimestamps);

    return {
      allowed: true,
      remaining: limit - validTimestamps.length,
      resetMs: windowMs
    };
  }

  clear(identifier?: string) {
    if (identifier) {
      this.windows.delete(identifier);
    } else {
      this.windows.clear();
    }
  }
}

export const defaultRateLimiter = new SlidingWindowRateLimiter();
