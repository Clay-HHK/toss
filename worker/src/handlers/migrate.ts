/**
 * Admin migration handlers.
 *
 * Secret-guarded: calls must carry `X-Migration-Secret: <env.MIGRATION_SECRET>`.
 * If the secret is not configured, the endpoint is disabled (503).
 *
 * Currently only implements T1-1 R2 key renaming. Future migrations should
 * add new dispatch branches rather than new routes, so ops only needs to know
 * one URL.
 */

import type { Env } from "../types";

interface MigrationReport {
  scanned: number;
  migrated: number;
  skipped: number;
  errors: Array<{ id: string; old_key: string; error: string }>;
}

/**
 * POST /api/v1/admin/migrate/r2-keys
 *
 * Query params:
 *   dry_run=1      report what would change without touching anything
 *   scope=documents|space_files|all   default: all
 *   limit=N        cap processed rows per scope (safety rail for first runs)
 *
 * Headers:
 *   X-Migration-Secret: <env.MIGRATION_SECRET>
 */
export async function handleMigrateR2Keys(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  _userId?: string,
): Promise<Response> {
  const configured = env.MIGRATION_SECRET;
  if (!configured) {
    return Response.json(
      {
        error: "Migration endpoint disabled",
        detail: "Set `MIGRATION_SECRET` via `wrangler secret put` to enable.",
      },
      { status: 503 },
    );
  }

  const supplied = req.headers.get("X-Migration-Secret");
  if (!supplied || !constantTimeEqual(supplied, configured)) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  const url = new URL(req.url);
  const dryRun = url.searchParams.get("dry_run") === "1"
    || url.searchParams.get("dry_run") === "true";
  const scope = url.searchParams.get("scope") ?? "all";
  const limitRaw = url.searchParams.get("limit");
  const limit = limitRaw ? Math.max(1, parseInt(limitRaw, 10) || 0) : 500;

  const result: Record<string, MigrationReport> = {};

  if (scope === "documents" || scope === "all") {
    result.documents = await migrateDocuments(env, dryRun, limit);
  }
  if (scope === "space_files" || scope === "all") {
    result.space_files = await migrateSpaceFiles(env, dryRun, limit);
  }

  return Response.json({ dry_run: dryRun, limit, scope, ...result });
}

/**
 * Migrate documents rows whose r2_key predates T1-1 (i.e. not `blobs/...`).
 * New key format is `blobs/${document_id}`.
 */
async function migrateDocuments(
  env: Env,
  dryRun: boolean,
  limit: number,
): Promise<MigrationReport> {
  const report: MigrationReport = { scanned: 0, migrated: 0, skipped: 0, errors: [] };

  const rows = await env.TOSS_DB
    .prepare(
      `SELECT id, r2_key, content_type FROM documents
       WHERE r2_key NOT LIKE 'blobs/%'
       LIMIT ?`,
    )
    .bind(limit)
    .all<{ id: string; r2_key: string; content_type: string | null }>();

  for (const row of rows.results) {
    report.scanned += 1;
    const newKey = `blobs/${row.id}`;
    if (row.r2_key === newKey) {
      report.skipped += 1;
      continue;
    }
    try {
      await copyAndSwap(
        env,
        row.r2_key,
        newKey,
        row.content_type ?? "application/octet-stream",
        dryRun,
        async () => {
          await env.TOSS_DB
            .prepare(`UPDATE documents SET r2_key = ? WHERE id = ?`)
            .bind(newKey, row.id)
            .run();
        },
      );
      report.migrated += 1;
    } catch (e) {
      report.errors.push({
        id: row.id,
        old_key: row.r2_key,
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }

  return report;
}

/**
 * Migrate space_files rows. New key format is `blobs/space/${id}` (the
 * space_file row id itself is a UUID so we reuse it).
 */
async function migrateSpaceFiles(
  env: Env,
  dryRun: boolean,
  limit: number,
): Promise<MigrationReport> {
  const report: MigrationReport = { scanned: 0, migrated: 0, skipped: 0, errors: [] };

  const rows = await env.TOSS_DB
    .prepare(
      `SELECT id, r2_key FROM space_files
       WHERE r2_key NOT LIKE 'blobs/space/%'
       LIMIT ?`,
    )
    .bind(limit)
    .all<{ id: string; r2_key: string }>();

  for (const row of rows.results) {
    report.scanned += 1;
    const newKey = `blobs/space/${row.id}`;
    if (row.r2_key === newKey) {
      report.skipped += 1;
      continue;
    }
    try {
      await copyAndSwap(
        env,
        row.r2_key,
        newKey,
        "application/octet-stream",
        dryRun,
        async () => {
          await env.TOSS_DB
            .prepare(`UPDATE space_files SET r2_key = ? WHERE id = ?`)
            .bind(newKey, row.id)
            .run();
        },
      );
      report.migrated += 1;
    } catch (e) {
      report.errors.push({
        id: row.id,
        old_key: row.r2_key,
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }

  return report;
}

/**
 * Read `oldKey` from R2, write its bytes to `newKey`, run the DB swap callback,
 * then delete `oldKey`. In dry-run mode, only the read is attempted (to prove
 * the old object exists) and nothing is mutated.
 *
 * Order matters: we update D1 *after* the new R2 object is in place and *before*
 * we delete the old object. If the process crashes mid-way, the worst case is
 * a dangling old object — never a row pointing at a nonexistent key.
 */
async function copyAndSwap(
  env: Env,
  oldKey: string,
  newKey: string,
  contentType: string,
  dryRun: boolean,
  swapRow: () => Promise<void>,
): Promise<void> {
  const src = await env.TOSS_STORAGE.get(oldKey);
  if (!src) {
    throw new Error(`R2 object missing: ${oldKey}`);
  }
  if (dryRun) return;

  const bytes = await src.arrayBuffer();
  await env.TOSS_STORAGE.put(newKey, bytes, {
    httpMetadata: { contentType },
  });
  await swapRow();
  await env.TOSS_STORAGE.delete(oldKey);
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}
