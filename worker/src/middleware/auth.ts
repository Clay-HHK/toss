/**
 * JWT authentication middleware.
 *
 * Uses HMAC-SHA256 for JWT signing/verification via Web Crypto API.
 *
 * Two token shapes flow through this module:
 *   - Auth JWT (`JWTPayload`) — issued at login, 30d lifetime, bearer auth.
 *   - Download ticket (`DownloadTicketPayload`) — minted per download, 5m
 *     lifetime, redeemed once via `/api/v1/blobs/:ticket` (T1-2).
 */

import type { DownloadTicketPayload, Env, JWTPayload } from "../types";

const JWT_ALGORITHM = { name: "HMAC", hash: "SHA-256" };
const JWT_EXPIRY_SECONDS = 30 * 24 * 60 * 60; // 30 days
// Download ticket TTL. Short enough that a leaked URL is nearly useless,
// long enough that a slow 4G upload-then-download round-trip still works.
export const DOWNLOAD_TICKET_TTL_SECONDS = 300;

export async function verifyJWT(token: string, env: Env): Promise<JWTPayload | null> {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    const [headerB64, payloadB64, signatureB64] = parts;
    const key = await importKey(env.JWT_SECRET);

    const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
    const signature = base64UrlDecode(signatureB64);

    const valid = await crypto.subtle.verify(JWT_ALGORITHM, key, signature, data);
    if (!valid) return null;

    const payload: JWTPayload = JSON.parse(
      new TextDecoder().decode(base64UrlDecode(payloadB64)),
    );

    if (payload.exp < Math.floor(Date.now() / 1000)) return null;

    // T1-4: honour the revocation blacklist. JTIs are kept in KV until the
    // underlying token's natural expiry, so a missing entry means "live".
    // Tokens minted before T1-4 have no jti — we pass those through so old
    // installs don't get logged out mid-session.
    if (payload.jti && env.TOSS_KV) {
      const revoked = await env.TOSS_KV.get(`revoked:${payload.jti}`);
      if (revoked !== null) return null;
    }

    return payload;
  } catch {
    return null;
  }
}

export async function signJWT(
  userId: string,
  githubUsername: string,
  env: Env,
  options: { deviceId?: string } = {},
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "HS256", typ: "JWT" };
  const payload: JWTPayload = {
    sub: userId,
    gh: githubUsername,
    iat: now,
    exp: now + JWT_EXPIRY_SECONDS,
    // T1-4: always mint a jti so the token can be individually revoked.
    jti: crypto.randomUUID(),
  };
  if (options.deviceId) {
    payload.dev = options.deviceId;
  }

  const headerB64 = base64UrlEncode(JSON.stringify(header));
  const payloadB64 = base64UrlEncode(JSON.stringify(payload));

  const key = await importKey(env.JWT_SECRET);
  const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = await crypto.subtle.sign(JWT_ALGORITHM, key, data);
  const signatureB64 = base64UrlEncodeBuffer(signature);

  return `${headerB64}.${payloadB64}.${signatureB64}`;
}

/**
 * T1-4: mark a JTI as revoked by writing it into the KV blacklist with a TTL
 * equal to the remaining life of the token. After `expireAt` the entry
 * self-deletes, keeping the blacklist small.
 */
export async function revokeJTI(
  jti: string,
  expireAt: number,
  env: Env,
): Promise<void> {
  const nowSec = Math.floor(Date.now() / 1000);
  const ttl = Math.max(60, expireAt - nowSec); // min 1 min as safety net
  await env.TOSS_KV.put(`revoked:${jti}`, "1", { expirationTtl: ttl });
}

export function extractBearerToken(request: Request): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return header.slice(7);
}

/**
 * T1-2: sign a short-lived download ticket. The ticket is structurally a JWT
 * (same header + HMAC), but carries `typ: "dl"` so redemption paths refuse
 * to confuse it with an auth token.
 */
export async function signDownloadTicket(
  userId: string,
  resource: { t: "doc" | "space"; id: string },
  requesterIp: string,
  env: Env,
): Promise<{ ticket: string; expiresIn: number }> {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "HS256", typ: "JWT" };
  const payload: DownloadTicketPayload = {
    typ: "dl",
    sub: userId,
    t: resource.t,
    id: resource.id,
    ip: requesterIp,
    iat: now,
    exp: now + DOWNLOAD_TICKET_TTL_SECONDS,
  };

  const headerB64 = base64UrlEncode(JSON.stringify(header));
  const payloadB64 = base64UrlEncode(JSON.stringify(payload));

  const key = await importKey(env.JWT_SECRET);
  const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = await crypto.subtle.sign(JWT_ALGORITHM, key, data);
  const signatureB64 = base64UrlEncodeBuffer(signature);

  return {
    ticket: `${headerB64}.${payloadB64}.${signatureB64}`,
    expiresIn: DOWNLOAD_TICKET_TTL_SECONDS,
  };
}

/**
 * T1-2: verify a download ticket. Returns the parsed payload iff:
 *   - the HMAC matches,
 *   - `typ === "dl"` (no reuse of auth tokens as download URLs),
 *   - the ticket is not expired,
 *   - the requester IP matches the IP captured at mint time.
 *
 * Returns `null` on any failure. Callers should treat that as 401.
 */
export async function verifyDownloadTicket(
  ticket: string,
  requesterIp: string,
  env: Env,
): Promise<DownloadTicketPayload | null> {
  try {
    const parts = ticket.split(".");
    if (parts.length !== 3) return null;

    const [headerB64, payloadB64, signatureB64] = parts;
    const key = await importKey(env.JWT_SECRET);

    const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
    const signature = base64UrlDecode(signatureB64);
    const valid = await crypto.subtle.verify(JWT_ALGORITHM, key, signature, data);
    if (!valid) return null;

    const payload = JSON.parse(
      new TextDecoder().decode(base64UrlDecode(payloadB64)),
    ) as DownloadTicketPayload;

    if (payload.typ !== "dl") return null;
    if (payload.exp < Math.floor(Date.now() / 1000)) return null;
    if (payload.ip !== requesterIp) return null;

    return payload;
  } catch {
    return null;
  }
}

/**
 * Best-effort IP extraction. Cloudflare always populates `CF-Connecting-IP`,
 * so the fallback chain is defensive (tests, wrangler dev). An empty string
 * is a hard fail — tickets are bound to a specific IP and "" never matches
 * a real connection.
 */
export function getRequesterIp(request: Request): string {
  return (
    request.headers.get("CF-Connecting-IP")
    ?? request.headers.get("X-Forwarded-For")?.split(",")[0].trim()
    ?? ""
  );
}

async function importKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    JWT_ALGORITHM,
    false,
    ["sign", "verify"],
  );
}

function base64UrlEncode(str: string): string {
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlEncodeBuffer(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(str: string): Uint8Array {
  const padded = str.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}
