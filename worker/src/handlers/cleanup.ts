/**
 * Expired document cleanup handler.
 */

import type { Env } from "../types";

/**
 * POST /api/v1/admin/cleanup
 * Manually trigger cleanup of expired documents (older than 30 days).
 */
export async function handleCleanupExpired(
  _req: Request,
  env: Env,
  _params: Record<string, string>,
  _userId?: string,
): Promise<Response> {
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

  // Find expired documents
  const expired = await env.TOSS_DB.prepare(
    `SELECT id, r2_key FROM documents WHERE created_at < ? AND status = 'pending'`,
  ).bind(thirtyDaysAgo).all();

  let cleaned = 0;
  for (const doc of expired.results) {
    // Delete from R2
    await env.TOSS_STORAGE.delete(doc.r2_key as string);
    // Update status
    await env.TOSS_DB.prepare(
      `UPDATE documents SET status = 'expired' WHERE id = ?`,
    ).bind(doc.id).run();
    cleaned++;
  }

  return Response.json({ cleaned }, { status: 200 });
}
