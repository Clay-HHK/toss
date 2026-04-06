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
}

export interface JWTPayload {
  sub: string; // user id
  gh: string; // github username
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
