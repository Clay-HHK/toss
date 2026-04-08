/**
 * Cloudflare Worker environment bindings and shared types.
 */

export interface Env {
  TOSS_DB: D1Database;
  TOSS_STORAGE: R2Bucket;
  TOSS_KV: KVNamespace;
  JWT_SECRET: string;
  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  /**
   * T1-5: base64url-encoded 32-byte AES-GCM key used for envelope
   * encryption of sensitive D1 text fields (currently `documents.message`).
   * Optional at runtime — if unset, fieldcrypt logs a warning and stores
   * plaintext so local dev stays unblocked. Provision in prod with
   * `wrangler secret put D1_ENCRYPTION_KEY`.
   */
  D1_ENCRYPTION_KEY?: string;
  /**
   * Secret gating `POST /api/v1/admin/migrate/r2-keys`. The endpoint is
   * disabled entirely when this is unset. Rotate or unset after migrations
   * complete.
   */
  MIGRATION_SECRET?: string;
}

export interface JWTPayload {
  sub: string; // user id
  gh: string; // github username
  iat: number;
  exp: number;
  /** T1-4: unique token id, used as the revocation-blacklist key in KV. */
  jti?: string;
  /** T1-4: client-supplied device id, recorded for audit / revoke flows. */
  dev?: string;
}

/**
 * T1-2: short-lived download ticket.
 *
 * Minted via `POST /api/v1/documents/inbox/:id/ticket` (or the space
 * equivalent), redeemed once via `GET /api/v1/blobs/:ticket`. The ticket
 * never authorises anything except the one resource it names, and it is
 * HMAC-signed with the same JWT secret so no extra key material is needed.
 */
export interface DownloadTicketPayload {
  typ: "dl"; // distinguishes tickets from auth tokens
  sub: string; // user id who minted the ticket (for audit)
  t: "doc" | "space"; // resource type
  id: string; // documents.id or space_files.id
  ip: string; // CF-Connecting-IP at mint time (for rebind check)
  iat: number;
  exp: number;
}

export interface UserRow {
  id: string;
  github_username: string;
  github_id: number;
  display_name: string | null;
  created_at: string;
  last_seen_at: string;
  // T2-3: Tier 2 public keys. All nullable — pre-enrollment users carry NULLs.
  public_key: string | null;
  signing_public_key: string | null;
  public_key_proof: string | null;
  public_key_issued_at: number | null;
  public_key_updated_at: string | null;
}

export interface ContactRow {
  id: string;
  owner_id: string;
  target_id: string;
  alias: string;
  created_at: string;
}

export interface DocumentRow {
  id: string;
  sender_id: string;
  recipient_id: string;
  filename: string;
  r2_key: string;
  size_bytes: number;
  content_type: string;
  content_sha256: string | null;
  message: string | null;
  status: string;
  created_at: string;
  pulled_at: string | null;
}

export interface SpaceRow {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  description: string | null;
  created_at: string;
}

export interface SpaceFileRow {
  id: string;
  space_id: string;
  path: string;
  r2_key: string;
  size_bytes: number;
  content_hash: string;
  uploaded_by: string;
  version: number;
  updated_at: string;
}

export interface GroupRow {
  id: string;
  name: string;
  slug: string;
  invite_code: string;
  owner_id: string;
  created_at: string;
}

export type RouteHandler = (
  req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
) => Promise<Response>;

export interface Route {
  method: string;
  pattern: URLPattern;
  handler: RouteHandler;
  requiresAuth: boolean;
}
