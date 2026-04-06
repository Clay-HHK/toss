/**
 * Document push/pull handlers with R2 storage.
 */

import { uploadToR2, downloadFromR2 } from "../services/storage";
import type { DocumentRow, Env } from "../types";

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

  // Resolve recipient: try alias first, then github username
  const resolved = await resolveRecipient(env, userId!, recipientName);
  if (!resolved) {
    return Response.json(
      { error: `Recipient "${recipientName}" not found` },
      { status: 404 },
    );
  }

  const docId = crypto.randomUUID();
  const r2Key = `documents/inbox/${resolved.id}/${docId}/${file.name}`;

  // Upload to R2
  const fileBytes = await file.arrayBuffer();
  await uploadToR2(env.TOSS_STORAGE, r2Key, fileBytes, file.type || "application/octet-stream");

  // Insert document record
  await env.TOSS_DB
    .prepare(
      `INSERT INTO documents (id, sender_id, recipient_id, filename, r2_key, size_bytes, content_type, message)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      docId,
      userId!,
      resolved.id,
      file.name,
      r2Key,
      fileBytes.byteLength,
      file.type || "application/octet-stream",
      message,
    )
    .run();

  return Response.json({
    id: docId,
    filename: file.name,
    recipient: resolved.github_username,
    size_bytes: fileBytes.byteLength,
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
      `SELECT d.id, d.filename, d.size_bytes, d.message, d.status, d.created_at,
              u.github_username as sender_username, u.display_name as sender_name
       FROM documents d
       JOIN users u ON d.sender_id = u.id
       WHERE d.recipient_id = ? AND d.status = 'pending'
       ORDER BY d.created_at DESC`,
    )
    .bind(userId!)
    .all();

  return Response.json({ documents: rows.results });
}

/**
 * GET /api/v1/documents/inbox/:id/download
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

  return new Response(object.body, {
    headers: {
      "Content-Type": doc.content_type,
      "Content-Disposition": `attachment; filename="${doc.filename}"`,
      "Content-Length": doc.size_bytes.toString(),
    },
  });
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
      `SELECT d.id, d.filename, d.size_bytes, d.message, d.status, d.created_at, d.pulled_at,
              u.github_username as recipient_username
       FROM documents d
       JOIN users u ON d.recipient_id = u.id
       WHERE d.sender_id = ?
       ORDER BY d.created_at DESC
       LIMIT 50`,
    )
    .bind(userId!)
    .all();

  return Response.json({ documents: rows.results });
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
