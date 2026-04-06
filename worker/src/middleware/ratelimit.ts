/**
 * Per-user rate limiting via KV.
 */

import type { Env } from "../types";

const LIMIT = 60; // requests per minute

export async function checkRateLimit(
  env: Env,
  userId: string,
): Promise<{ allowed: boolean; remaining: number }> {
  const minute = Math.floor(Date.now() / 60000);
  const key = `ratelimit:${userId}:${minute}`;

  const current = await env.TOSS_KV.get(key);
  const count = current ? parseInt(current, 10) : 0;

  if (count >= LIMIT) {
    return { allowed: false, remaining: 0 };
  }

  await env.TOSS_KV.put(key, String(count + 1), { expirationTtl: 120 });
  return { allowed: true, remaining: LIMIT - count - 1 };
}
