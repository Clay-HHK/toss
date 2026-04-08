/**
 * T1-2: download-ticket redemption.
 *
 * `GET /api/v1/blobs/:ticket` is the single entry point for ticket-authorised
 * downloads. The route is registered with `requiresAuth: false` because the
 * ticket itself is the proof of authorisation — a 5-minute HMAC JWT bound to
 * the caller's IP that names exactly one resource.
 *
 * This handler:
 *   1. Parses + HMAC-verifies the ticket.
 *   2. Checks that the redeemer IP matches the IP captured at mint time.
 *   3. Looks up the resource (`doc` or `space` file).
 *   4. Streams R2 body with `Content-Disposition`, `X-Content-SHA256`,
 *      and the full set of strict security headers (added in `cors.ts`).
 *
 * The handler deliberately does NOT mark documents as `pulled` — the intent
 * is that callers may redeem a ticket multiple times within its five-minute
 * window (e.g. retry a flaky download). Marking "pulled" stays on the legacy
 * `/download` route. We can revisit this once the legacy route is removed.
 */

import { getRequesterIp, verifyDownloadTicket } from "../middleware/auth";
import { downloadFromR2 } from "../services/storage";
import type { DocumentRow, Env, SpaceFileRow } from "../types";

export async function handleRedeemBlobTicket(
  req: Request,
  env: Env,
  params: Record<string, string>,
  _userId?: string,
): Promise<Response> {
  const ticket = params.ticket;
  if (!ticket) {
    return Response.json({ error: "ticket required" }, { status: 400 });
  }

  const requesterIp = getRequesterIp(req);
  if (!requesterIp) {
    return Response.json(
      { error: "Unable to determine requester IP" },
      { status: 400 },
    );
  }

  const payload = await verifyDownloadTicket(ticket, requesterIp, env);
  if (!payload) {
    return Response.json(
      { error: "Ticket invalid, expired, or IP mismatch" },
      { status: 401 },
    );
  }

  if (payload.t === "doc") {
    return streamDocumentBlob(env, payload.id, payload.sub);
  }
  if (payload.t === "space") {
    return streamSpaceFileBlob(env, payload.id);
  }
  return Response.json({ error: "Unknown ticket resource type" }, { status: 400 });
}

async function streamDocumentBlob(
  env: Env,
  docId: string,
  recipientId: string,
): Promise<Response> {
  // We still cross-check recipient_id: a ticket minted by user A must not
  // survive the revocation of A's access to the row. It's cheap insurance.
  const doc = await env.TOSS_DB
    .prepare("SELECT * FROM documents WHERE id = ? AND recipient_id = ?")
    .bind(docId, recipientId)
    .first<DocumentRow>();

  if (!doc) {
    return Response.json({ error: "Document not found" }, { status: 404 });
  }

  const object = await downloadFromR2(env.TOSS_STORAGE, doc.r2_key);
  if (!object) {
    return Response.json({ error: "File not found in storage" }, { status: 404 });
  }

  const headers: Record<string, string> = {
    "Content-Type": doc.content_type,
    "Content-Disposition": `attachment; filename="${doc.filename}"`,
    "Content-Length": doc.size_bytes.toString(),
  };
  if (doc.content_sha256) {
    headers["X-Content-SHA256"] = doc.content_sha256;
  }

  return new Response(object.body, { headers });
}

async function streamSpaceFileBlob(env: Env, fileId: string): Promise<Response> {
  const fileRow = await env.TOSS_DB
    .prepare("SELECT * FROM space_files WHERE id = ?")
    .bind(fileId)
    .first<SpaceFileRow>();

  if (!fileRow) {
    return Response.json({ error: "File not found" }, { status: 404 });
  }

  const object = await downloadFromR2(env.TOSS_STORAGE, fileRow.r2_key);
  if (!object) {
    return Response.json({ error: "File not found in storage" }, { status: 404 });
  }

  const filename = fileRow.path.split("/").pop() || "file";

  const headers: Record<string, string> = {
    "Content-Type": "application/octet-stream",
    "Content-Disposition": `attachment; filename="${filename}"`,
    "Content-Length": fileRow.size_bytes.toString(),
  };
  if (fileRow.content_hash) {
    headers["X-Content-SHA256"] = fileRow.content_hash;
  }

  return new Response(object.body, { headers });
}
