/**
 * Document push/pull handlers with R2 storage.
 */

import { getRequesterIp, signDownloadTicket } from "../middleware/auth";
import { decryptField, decryptFields, encryptField } from "../services/fieldcrypt";
import { uploadToR2, downloadFromR2 } from "../services/storage";
import type { DocumentRow, Env } from "../types";

/**
 * Compute lowercase SHA-256 hex digest of a byte buffer.
 */
async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Normalize a client-supplied SHA-256 string.
 * Accepts lowercase hex of length 64; returns null on any mismatch.
 */
function normalizeSha256(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const trimmed = raw.trim().toLowerCase();
  if (trimmed.length !== 64) return null;
  if (!/^[0-9a-f]{64}$/.test(trimmed)) return null;
  return trimmed;
}

/**
 * POST /api/v1/documents/push
 * Multipart form: file, recipient, message (optional)
 */
export async function handlePushDocument(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const formData = await req.formData();
  const file = formData.get("file") as File | null;
  const recipientName = formData.get("recipient") as string | null;
  const message = formData.get("message") as string | null;

  if (!file) {
    return Response.json({ error: "file is required" }, { status: 400 });
  }
  if (!recipientName) {
    return Response.json({ error: "recipient is required" }, { status: 400 });
  }

  // File size limit: 50MB
  const MAX_FILE_SIZE = 50 * 1024 * 1024;
  if (file.size > MAX_FILE_SIZE) {
    return Response.json(
      { error: "File too large", detail: "Maximum file size is 50MB" },
      { status: 413 },
    );
  }

  // Resolve recipient: try alias first, then github username
  const resolved = await resolveRecipient(env, userId!, recipientName);
  if (!resolved) {
    return Response.json(
      { error: `Recipient "${recipientName}" not found` },
      { status: 404 },
    );
  }

  const docId = crypto.randomUUID();
  // T1-1: opaque R2 key. The previous format leaked recipient_id and the
  // original filename in the bucket listing — anyone who stole an R2 token
  // could enumerate "who has what". The real filename is preserved in
  // documents.filename and re-emitted via Content-Disposition on download.
  const r2Key = `blobs/${docId}`;

  // Upload to R2
  const fileBytes = await file.arrayBuffer();
  await uploadToR2(env.TOSS_STORAGE, r2Key, fileBytes, file.type || "application/octet-stream");

  // T1-3: end-to-end SHA-256. Prefer client-supplied hash (verify matches bytes
  // the server received); fall back to server-side compute for legacy clients.
  const clientHash = normalizeSha256(formData.get("content_sha256") as string | null);
  const serverHash = await sha256Hex(fileBytes);
  if (clientHash && clientHash !== serverHash) {
    return Response.json(
      {
        error: "content_sha256 mismatch",
        detail: "Upload bytes do not match client-supplied hash",
      },
      { status: 400 },
    );
  }
  const contentSha256 = clientHash ?? serverHash;

  // T1-5: envelope-encrypt the free-form `message` before persisting.
  // encryptField is a no-op for null/empty and for missing key (dev mode).
  const storedMessage = await encryptField(message, env.D1_ENCRYPTION_KEY);

  // Insert document record
  await env.TOSS_DB
    .prepare(
      `INSERT INTO documents (id, sender_id, recipient_id, filename, r2_key, size_bytes, content_type, content_sha256, message)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      docId,
      userId!,
      resolved.id,
      file.name,
      r2Key,
      fileBytes.byteLength,
      file.type || "application/octet-stream",
      contentSha256,
      storedMessage,
    )
    .run();

  return Response.json({
    id: docId,
    filename: file.name,
    recipient: resolved.github_username,
    size_bytes: fileBytes.byteLength,
    content_sha256: contentSha256,
    status: "delivered",
  }, { status: 201 });
}

/**
 * GET /api/v1/documents/inbox
 */
export async function handleListInbox(
  _req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const rows = await env.TOSS_DB
    .prepare(
      `SELECT d.id, d.filename, d.size_bytes, d.content_sha256, d.message, d.status, d.created_at,
              u.github_username as sender_username, u.display_name as sender_name
       FROM documents d
       JOIN users u ON d.sender_id = u.id
       WHERE d.recipient_id = ? AND d.status = 'pending'
       ORDER BY d.created_at DESC`,
    )
    .bind(userId!)
    .all<{ message: string | null } & Record<string, unknown>>();

  // T1-5: decrypt `message` in place. Plaintext / legacy rows pass through
  // unchanged because `decryptField` keys off the `enc:v1:` prefix.
  const messages = await decryptFields(
    rows.results.map((r) => (r.message as string | null) ?? null),
    env.D1_ENCRYPTION_KEY,
  );
  const decrypted = rows.results.map((r, i) => ({ ...r, message: messages[i] }));

  return Response.json({ documents: decrypted });
}

/**
 * POST /api/v1/documents/inbox/:id/ticket
 *
 * T1-2: mint a 5-minute single-resource download ticket. The returned `url`
 * is a complete path into `/api/v1/blobs/:ticket`; the client just has to
 * GET it with no extra headers (the ticket is self-authenticating).
 *
 * The blast radius of a leaked ticket is one document for five minutes from
 * the minting IP — orders of magnitude smaller than the 30d auth JWT.
 */
export async function handleMintDocumentTicket(
  req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const docId = params.id;

  const doc = await env.TOSS_DB
    .prepare("SELECT id FROM documents WHERE id = ? AND recipient_id = ?")
    .bind(docId, userId!)
    .first<{ id: string }>();

  if (!doc) {
    return Response.json({ error: "Document not found" }, { status: 404 });
  }

  const ip = getRequesterIp(req);
  if (!ip) {
    return Response.json(
      { error: "Unable to determine requester IP for ticket binding" },
      { status: 400 },
    );
  }

  const { ticket, expiresIn } = await signDownloadTicket(
    userId!,
    { t: "doc", id: docId },
    ip,
    env,
  );

  return Response.json({
    url: `/api/v1/blobs/${ticket}`,
    expires_in: expiresIn,
  });
}

/**
 * GET /api/v1/documents/inbox/:id/download
 *
 * LEGACY path kept for one release cycle after T1-2 shipped. New clients
 * should mint a ticket first. Legacy clients see a `X-Deprecated` header
 * nudging them to upgrade.
 */
export async function handleDownloadDocument(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const docId = params.id;

  const doc = await env.TOSS_DB
    .prepare("SELECT * FROM documents WHERE id = ? AND recipient_id = ?")
    .bind(docId, userId!)
    .first<DocumentRow>();

  if (!doc) {
    return Response.json({ error: "Document not found" }, { status: 404 });
  }

  // Get file from R2
  const object = await downloadFromR2(env.TOSS_STORAGE, doc.r2_key);
  if (!object) {
    return Response.json({ error: "File not found in storage" }, { status: 404 });
  }

  // Mark as pulled
  await env.TOSS_DB
    .prepare("UPDATE documents SET status = 'pulled', pulled_at = datetime('now') WHERE id = ?")
    .bind(docId)
    .run();

  const headers: Record<string, string> = {
    "Content-Type": doc.content_type,
    "Content-Disposition": `attachment; filename="${doc.filename}"`,
    "Content-Length": doc.size_bytes.toString(),
    // Nudge clients toward the ticket flow; the legacy route will be removed
    // once a full release has passed with ticket-capable clients.
    "X-Deprecated": "Use POST /api/v1/documents/inbox/:id/ticket then GET /api/v1/blobs/:ticket",
  };
  // T1-3: publish SHA-256 so the client can verify end-to-end integrity.
  if (doc.content_sha256) {
    headers["X-Content-SHA256"] = doc.content_sha256;
  }

  return new Response(object.body, { headers });
}

/**
 * GET /api/v1/documents/inbox/:id/preview
 * Returns file content as text (for text files) or base64 (for binary).
 * Does NOT mark as pulled.
 */
export async function handlePreviewDocument(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const docId = params.id;

  const doc = await env.TOSS_DB
    .prepare("SELECT * FROM documents WHERE id = ? AND recipient_id = ?")
    .bind(docId, userId!)
    .first<DocumentRow>();

  if (!doc) {
    return Response.json({ error: "Document not found" }, { status: 404 });
  }

  const object = await downloadFromR2(env.TOSS_STORAGE, doc.r2_key);
  if (!object) {
    return Response.json({ error: "File not found in storage" }, { status: 404 });
  }

  const bytes = await object.arrayBuffer();
  const isText = (doc.content_type || "").startsWith("text/")
    || ["application/json", "application/yaml", "application/xml"].some(
      t => (doc.content_type || "").includes(t),
    );

  // Limit preview to 64KB
  const maxPreview = 64 * 1024;
  const truncated = bytes.byteLength > maxPreview;
  const slice = truncated ? bytes.slice(0, maxPreview) : bytes;

  if (isText) {
    const text = new TextDecoder("utf-8", { fatal: false }).decode(slice);
    return Response.json({
      filename: doc.filename,
      content_type: doc.content_type,
      size_bytes: doc.size_bytes,
      preview_type: "text",
      content: text,
      truncated,
    });
  }

  // Binary: return base64
  const b64 = btoa(
    Array.from(new Uint8Array(slice), b => String.fromCharCode(b)).join(""),
  );
  return Response.json({
    filename: doc.filename,
    content_type: doc.content_type,
    size_bytes: doc.size_bytes,
    preview_type: "binary",
    content: b64,
    truncated,
  });
}

/**
 * DELETE /api/v1/documents/inbox/:id
 * Dismiss a document from inbox without pulling.
 */
export async function handleDeleteDocument(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const docId = params.id;

  const doc = await env.TOSS_DB
    .prepare("SELECT id, r2_key FROM documents WHERE id = ? AND recipient_id = ?")
    .bind(docId, userId!)
    .first<{ id: string; r2_key: string }>();

  if (!doc) {
    return Response.json({ error: "Document not found" }, { status: 404 });
  }

  // Delete from R2
  await env.TOSS_STORAGE.delete(doc.r2_key);

  // Delete from D1
  await env.TOSS_DB
    .prepare("DELETE FROM documents WHERE id = ?")
    .bind(docId)
    .run();

  return Response.json({ deleted: true, id: docId });
}

/**
 * GET /api/v1/documents/sent
 */
export async function handleListSent(
  _req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const rows = await env.TOSS_DB
    .prepare(
      `SELECT d.id, d.filename, d.size_bytes, d.content_sha256, d.message, d.status, d.created_at, d.pulled_at,
              u.github_username as recipient_username
       FROM documents d
       JOIN users u ON d.recipient_id = u.id
       WHERE d.sender_id = ?
       ORDER BY d.created_at DESC
       LIMIT 50`,
    )
    .bind(userId!)
    .all<{ message: string | null } & Record<string, unknown>>();

  // T1-5: same decrypt path as inbox.
  const messages = await decryptFields(
    rows.results.map((r) => (r.message as string | null) ?? null),
    env.D1_ENCRYPTION_KEY,
  );
  const decrypted = rows.results.map((r, i) => ({ ...r, message: messages[i] }));

  return Response.json({ documents: decrypted });
}

async function resolveRecipient(
  env: Env,
  ownerId: string,
  name: string,
): Promise<{ id: string; github_username: string } | null> {
  // Try alias first
  const byAlias = await env.TOSS_DB
    .prepare(
      `SELECT c.target_id as id, u.github_username
       FROM contacts c
       JOIN users u ON c.target_id = u.id
       WHERE c.owner_id = ? AND c.alias = ?`,
    )
    .bind(ownerId, name)
    .first<{ id: string; github_username: string }>();

  if (byAlias) return byAlias;

  // Fall back to github username
  const byUsername = await env.TOSS_DB
    .prepare("SELECT id, github_username FROM users WHERE github_username = ?")
    .bind(name)
    .first<{ id: string; github_username: string }>();

  return byUsername ?? null;
}
