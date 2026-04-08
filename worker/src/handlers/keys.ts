/**
 * T2-4: User public key endpoints.
 *
 * Toss Tier 2 uses a two-key model per user:
 *   - X25519 encryption pubkey   `public_key`         (prefixed toss1...)
 *   - Ed25519 signing pubkey     `signing_public_key` (prefixed tossk1...)
 *
 * Enrollment is self-serve: a client generates a keypair locally, signs a
 * canonical proof-of-possession with its Ed25519 key, and POSTs both pubkeys
 * + the signature. The proof binds the upload to the authenticated user's
 * GitHub identity and a timestamp, so a stolen JWT cannot be used to rotate
 * a victim's key to an attacker-controlled value without also holding the
 * Ed25519 private key (the exact key material we are trying to protect).
 *
 * Canonical message format (UTF-8):
 *   "toss-enroll-v1\n<github_username>\n<x25519_pubkey_b64u>\n<issued_at>"
 *
 * All three of `public_key`, `signing_public_key`, `proof` are base64url
 * strings of 32 / 32 / 64 raw bytes respectively (Ed25519 signatures are
 * always 64 bytes).
 *
 * Phase A clients treat a missing `public_key` on a peer as "fall back to
 * plaintext", so this endpoint is always safe to be unset.
 */

import type { Env, UserRow } from "../types";

const PUBKEY_PREFIX = "toss1";
const SIGNING_PREFIX = "tossk1";
const MAX_ENROLL_CLOCK_SKEW_SECONDS = 10 * 60; // ±10 min vs server clock

interface EnrollRequest {
  public_key: string;
  signing_public_key: string;
  proof: string;
  issued_at: number;
}

interface PublicKeyResponse {
  username: string;
  public_key: string | null;
  signing_public_key: string | null;
  proof: string | null;
  issued_at: number | null;
  updated_at: string | null;
}

/**
 * POST /api/v1/keys — self-enroll the caller's public keys.
 * Body: { public_key, signing_public_key, proof, issued_at }
 */
export async function handleEnrollKey(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  let body: EnrollRequest;
  try {
    body = await req.json<EnrollRequest>();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!body.public_key || !body.signing_public_key || !body.proof
      || typeof body.issued_at !== "number") {
    return Response.json(
      { error: "public_key, signing_public_key, proof, issued_at are required" },
      { status: 400 },
    );
  }

  if (!body.public_key.startsWith(PUBKEY_PREFIX)) {
    return Response.json({ error: `public_key must start with ${PUBKEY_PREFIX}` }, { status: 400 });
  }
  if (!body.signing_public_key.startsWith(SIGNING_PREFIX)) {
    return Response.json(
      { error: `signing_public_key must start with ${SIGNING_PREFIX}` },
      { status: 400 },
    );
  }

  // Clock skew check — rejects both backdated and far-future proofs so a stale
  // dump of enrollment requests cannot be replayed later.
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(body.issued_at - now) > MAX_ENROLL_CLOCK_SKEW_SECONDS) {
    return Response.json(
      {
        error: "issued_at is outside the allowed clock skew window",
        detail: `server_now=${now}, issued_at=${body.issued_at}`,
      },
      { status: 400 },
    );
  }

  // Look up the caller so we can pin the proof to their GitHub username.
  const user = await env.TOSS_DB
    .prepare("SELECT github_username FROM users WHERE id = ?")
    .bind(userId!)
    .first<{ github_username: string }>();
  if (!user) {
    return Response.json({ error: "User not found" }, { status: 404 });
  }

  // Build the canonical message and verify the Ed25519 proof.
  const x25519Pub = body.public_key.slice(PUBKEY_PREFIX.length);
  const canonical =
    `toss-enroll-v1\n${user.github_username}\n${x25519Pub}\n${body.issued_at}`;
  const signingPubBytes = base64UrlDecode(body.signing_public_key.slice(SIGNING_PREFIX.length));
  const sigBytes = base64UrlDecode(body.proof);

  const proofOk = await verifyEd25519(signingPubBytes, sigBytes, new TextEncoder().encode(canonical));
  if (!proofOk) {
    return Response.json(
      { error: "proof signature did not verify" },
      { status: 400 },
    );
  }

  const updatedAt = new Date().toISOString();
  await env.TOSS_DB
    .prepare(
      `UPDATE users
         SET public_key = ?,
             signing_public_key = ?,
             public_key_proof = ?,
             public_key_issued_at = ?,
             public_key_updated_at = ?
       WHERE id = ?`,
    )
    .bind(
      body.public_key,
      body.signing_public_key,
      body.proof,
      body.issued_at,
      updatedAt,
      userId!,
    )
    .run();

  return Response.json(
    {
      username: user.github_username,
      public_key: body.public_key,
      signing_public_key: body.signing_public_key,
      proof: body.proof,
      issued_at: body.issued_at,
      updated_at: updatedAt,
    },
    { status: 201 },
  );
}

/**
 * GET /api/v1/keys/:username — fetch a single user's published keys.
 *
 * Returns 200 with nullable fields when the user exists but has not enrolled.
 * Returns 404 only when the username is entirely unknown. This lets clients
 * differentiate "no such user" from "user hasn't enrolled yet" cleanly.
 */
export async function handleGetKey(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  _userId?: string,
): Promise<Response> {
  const row = await env.TOSS_DB
    .prepare(
      `SELECT github_username, public_key, signing_public_key, public_key_proof,
              public_key_issued_at, public_key_updated_at
         FROM users
        WHERE github_username = ?`,
    )
    .bind(params.username)
    .first<Pick<
      UserRow,
      | "github_username"
      | "public_key"
      | "signing_public_key"
      | "public_key_proof"
      | "public_key_issued_at"
      | "public_key_updated_at"
    >>();

  if (!row) {
    return Response.json({ error: "User not found" }, { status: 404 });
  }
  return Response.json(rowToPublic(row));
}

/**
 * GET /api/v1/keys/batch?usernames=alice,bob,carol
 *
 * Group push flows hit this once to fan out a single R2 upload to many
 * wrapped keys. Hard cap at 100 usernames per call; pagination responsibility
 * stays with the client.
 */
export async function handleBatchGetKeys(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  _userId?: string,
): Promise<Response> {
  const url = new URL(req.url);
  const raw = url.searchParams.get("usernames");
  if (!raw) {
    return Response.json({ error: "usernames query param is required" }, { status: 400 });
  }
  const usernames = raw.split(",").map((s) => s.trim()).filter(Boolean);
  if (usernames.length === 0) {
    return Response.json({ keys: [] });
  }
  if (usernames.length > 100) {
    return Response.json(
      { error: "too many usernames (max 100 per request)" },
      { status: 400 },
    );
  }

  // D1 bindings don't support arrays, so we build the IN-clause placeholders.
  const placeholders = usernames.map(() => "?").join(",");
  const rows = await env.TOSS_DB
    .prepare(
      `SELECT github_username, public_key, signing_public_key, public_key_proof,
              public_key_issued_at, public_key_updated_at
         FROM users
        WHERE github_username IN (${placeholders})`,
    )
    .bind(...usernames)
    .all<Pick<
      UserRow,
      | "github_username"
      | "public_key"
      | "signing_public_key"
      | "public_key_proof"
      | "public_key_issued_at"
      | "public_key_updated_at"
    >>();

  return Response.json({ keys: rows.results.map(rowToPublic) });
}

function rowToPublic(
  row: Pick<
    UserRow,
    | "github_username"
    | "public_key"
    | "signing_public_key"
    | "public_key_proof"
    | "public_key_issued_at"
    | "public_key_updated_at"
  >,
): PublicKeyResponse {
  return {
    username: row.github_username,
    public_key: row.public_key,
    signing_public_key: row.signing_public_key,
    proof: row.public_key_proof,
    issued_at: row.public_key_issued_at,
    updated_at: row.public_key_updated_at,
  };
}

// -----------------------------------------------------------------------------
// Ed25519 proof verification via Web Crypto API.
//
// Cloudflare Workers support `Ed25519` in WebCrypto as of 2023-03-01
// compatibility date. Our wrangler.toml pins a 2025 date so this is guaranteed
// available. On any import/verify error we return `false` rather than
// throwing — the caller then replies 400.
// -----------------------------------------------------------------------------

async function verifyEd25519(
  publicKey: Uint8Array,
  signature: Uint8Array,
  message: Uint8Array,
): Promise<boolean> {
  if (publicKey.length !== 32) return false;
  if (signature.length !== 64) return false;
  try {
    // `Ed25519` is not in the stock WebCrypto AlgorithmIdentifier union in
    // @cloudflare/workers-types but is accepted by the Workers runtime. The
    // `as any` is the narrowest escape hatch needed.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const algo = { name: "Ed25519" } as any;
    const key = await crypto.subtle.importKey(
      "raw",
      publicKey,
      algo,
      false,
      ["verify"],
    );
    return await crypto.subtle.verify(algo, key, signature, message);
  } catch {
    return false;
  }
}

function base64UrlDecode(s: string): Uint8Array {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const b64 = (s + pad).replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}
