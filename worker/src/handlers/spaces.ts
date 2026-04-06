/**
 * Shared Spaces handlers: create, list, add members, sync, upload, download.
 */

import { uploadToR2, downloadFromR2 } from "../services/storage";
import type { Env, SpaceRow, SpaceFileRow } from "../types";

/**
 * Verify that a user is the owner or a member of the space identified by slug.
 * Returns the space row if authorized, otherwise null.
 */
async function verifySpaceMembership(
  env: Env,
  spaceSlug: string,
  userId: string,
): Promise<SpaceRow | null> {
  const space = await env.TOSS_DB
    .prepare("SELECT * FROM spaces WHERE slug = ?")
    .bind(spaceSlug)
    .first<SpaceRow>();

  if (!space) return null;

  // Owner always has access
  if (space.owner_id === userId) return space;

  // Check membership
  const member = await env.TOSS_DB
    .prepare("SELECT 1 FROM space_members WHERE space_id = ? AND user_id = ?")
    .bind(space.id, userId)
    .first();

  return member ? space : null;
}

/**
 * POST /api/v1/spaces
 * Body: { name, slug, description? }
 */
export async function handleCreateSpace(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const body = await req.json<{ name?: string; slug?: string; description?: string }>();

  if (!body.name || !body.slug) {
    return Response.json({ error: "name and slug are required" }, { status: 400 });
  }

  const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  if (!slugPattern.test(body.slug)) {
    return Response.json(
      { error: "slug must be lowercase alphanumeric with hyphens" },
      { status: 400 },
    );
  }

  // Check slug uniqueness
  const existing = await env.TOSS_DB
    .prepare("SELECT id FROM spaces WHERE slug = ?")
    .bind(body.slug)
    .first();

  if (existing) {
    return Response.json({ error: "slug already taken" }, { status: 409 });
  }

  const spaceId = crypto.randomUUID();

  await env.TOSS_DB
    .prepare(
      `INSERT INTO spaces (id, name, slug, owner_id, description)
       VALUES (?, ?, ?, ?, ?)`,
    )
    .bind(spaceId, body.name, body.slug, userId!, body.description || null)
    .run();

  return Response.json({
    id: spaceId,
    name: body.name,
    slug: body.slug,
    owner_id: userId!,
    description: body.description || null,
  }, { status: 201 });
}

/**
 * GET /api/v1/spaces
 * List spaces where user is owner or member.
 */
export async function handleListSpaces(
  _req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const rows = await env.TOSS_DB
    .prepare(
      `SELECT s.id, s.name, s.slug, s.description, s.created_at,
              u.github_username as owner_username,
              CASE WHEN s.owner_id = ? THEN 'owner' ELSE 'member' END as role
       FROM spaces s
       JOIN users u ON s.owner_id = u.id
       WHERE s.owner_id = ?
          OR s.id IN (SELECT space_id FROM space_members WHERE user_id = ?)
       ORDER BY s.created_at DESC`,
    )
    .bind(userId!, userId!, userId!)
    .all();

  return Response.json({ spaces: rows.results });
}

/**
 * POST /api/v1/spaces/:slug/members
 * Body: { github_username }
 */
export async function handleAddMember(
  req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const slug = params.slug;
  const body = await req.json<{ github_username?: string }>();

  if (!body.github_username) {
    return Response.json({ error: "github_username is required" }, { status: 400 });
  }

  // Verify requester is owner
  const space = await env.TOSS_DB
    .prepare("SELECT * FROM spaces WHERE slug = ?")
    .bind(slug)
    .first<SpaceRow>();

  if (!space) {
    return Response.json({ error: "Space not found" }, { status: 404 });
  }

  if (space.owner_id !== userId!) {
    return Response.json({ error: "Only the space owner can add members" }, { status: 403 });
  }

  // Lookup target user
  const targetUser = await env.TOSS_DB
    .prepare("SELECT id, github_username FROM users WHERE github_username = ?")
    .bind(body.github_username)
    .first<{ id: string; github_username: string }>();

  if (!targetUser) {
    return Response.json(
      { error: `User "${body.github_username}" not found` },
      { status: 404 },
    );
  }

  // Prevent adding self
  if (targetUser.id === userId!) {
    return Response.json({ error: "Cannot add yourself as a member" }, { status: 400 });
  }

  // Check if already a member
  const existing = await env.TOSS_DB
    .prepare("SELECT 1 FROM space_members WHERE space_id = ? AND user_id = ?")
    .bind(space.id, targetUser.id)
    .first();

  if (existing) {
    return Response.json({ error: "User is already a member" }, { status: 409 });
  }

  await env.TOSS_DB
    .prepare("INSERT INTO space_members (space_id, user_id, role) VALUES (?, ?, 'member')")
    .bind(space.id, targetUser.id)
    .run();

  return Response.json({
    space: space.slug,
    member: targetUser.github_username,
    role: "member",
  }, { status: 201 });
}

/**
 * POST /api/v1/spaces/:slug/sync
 * Body: { manifest: [{ path, content_hash }] }
 * Returns: { to_download, to_upload, conflicts }
 */
export async function handleSyncSpace(
  req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const slug = params.slug;
  const space = await verifySpaceMembership(env, slug, userId!);

  if (!space) {
    return Response.json({ error: "Space not found or access denied" }, { status: 404 });
  }

  const body = await req.json<{
    manifest: Array<{ path: string; content_hash: string }>;
  }>();

  if (!body.manifest || !Array.isArray(body.manifest)) {
    return Response.json({ error: "manifest array is required" }, { status: 400 });
  }

  // Get all server files for this space
  const serverFilesResult = await env.TOSS_DB
    .prepare("SELECT path, content_hash, size_bytes, version FROM space_files WHERE space_id = ?")
    .bind(space.id)
    .all<{ path: string; content_hash: string; size_bytes: number; version: number }>();

  const serverFiles = new Map<string, { content_hash: string; size_bytes: number; version: number }>();
  for (const row of serverFilesResult.results) {
    serverFiles.set(row.path, {
      content_hash: row.content_hash,
      size_bytes: row.size_bytes,
      version: row.version,
    });
  }

  // Build local manifest map
  const localFiles = new Map<string, string>();
  for (const entry of body.manifest) {
    localFiles.set(entry.path, entry.content_hash);
  }

  const to_download: Array<{ path: string; content_hash: string; size_bytes: number }> = [];
  const to_upload: string[] = [];
  const conflicts: Array<{ path: string; local_hash: string; server_hash: string }> = [];

  // Files on server but not locally, or server has different hash
  for (const [path, server] of serverFiles) {
    const localHash = localFiles.get(path);
    if (localHash === undefined) {
      // Server has file, client doesn't -> download
      to_download.push({ path, content_hash: server.content_hash, size_bytes: server.size_bytes });
    } else if (localHash !== server.content_hash) {
      // Both have the file but hashes differ -> conflict
      conflicts.push({ path, local_hash: localHash, server_hash: server.content_hash });
    }
    // If hashes match, file is in sync
  }

  // Files locally but not on server -> upload
  for (const [path] of localFiles) {
    if (!serverFiles.has(path)) {
      to_upload.push(path);
    }
  }

  return Response.json({ to_download, to_upload, conflicts });
}

/**
 * POST /api/v1/spaces/:slug/files/upload
 * Multipart: file + path field
 */
export async function handleUploadSpaceFile(
  req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const slug = params.slug;
  const space = await verifySpaceMembership(env, slug, userId!);

  if (!space) {
    return Response.json({ error: "Space not found or access denied" }, { status: 404 });
  }

  const formData = await req.formData();
  const file = formData.get("file") as File | null;
  const filePath = formData.get("path") as string | null;

  if (!file) {
    return Response.json({ error: "file is required" }, { status: 400 });
  }
  if (!filePath) {
    return Response.json({ error: "path is required" }, { status: 400 });
  }

  const fileBytes = await file.arrayBuffer();
  const r2Key = `spaces/${space.id}/${filePath}`;

  // Compute content hash
  const hashBuffer = await crypto.subtle.digest("SHA-256", fileBytes);
  const contentHash = Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");

  // Upload to R2
  await uploadToR2(
    env.TOSS_STORAGE,
    r2Key,
    fileBytes,
    file.type || "application/octet-stream",
  );

  // Upsert space_files row
  const existing = await env.TOSS_DB
    .prepare("SELECT id, version FROM space_files WHERE space_id = ? AND path = ?")
    .bind(space.id, filePath)
    .first<{ id: string; version: number }>();

  if (existing) {
    await env.TOSS_DB
      .prepare(
        `UPDATE space_files
         SET r2_key = ?, size_bytes = ?, content_hash = ?, uploaded_by = ?,
             version = ?, updated_at = datetime('now')
         WHERE id = ?`,
      )
      .bind(r2Key, fileBytes.byteLength, contentHash, userId!, existing.version + 1, existing.id)
      .run();
  } else {
    const fileId = crypto.randomUUID();
    await env.TOSS_DB
      .prepare(
        `INSERT INTO space_files (id, space_id, path, r2_key, size_bytes, content_hash, uploaded_by, version)
         VALUES (?, ?, ?, ?, ?, ?, ?, 1)`,
      )
      .bind(fileId, space.id, filePath, r2Key, fileBytes.byteLength, contentHash, userId!)
      .run();
  }

  return Response.json({
    path: filePath,
    content_hash: contentHash,
    size_bytes: fileBytes.byteLength,
    version: existing ? existing.version + 1 : 1,
  }, { status: 201 });
}

/**
 * GET /api/v1/spaces/:slug/files/download?path=...
 */
export async function handleDownloadSpaceFile(
  req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const slug = params.slug;
  const space = await verifySpaceMembership(env, slug, userId!);

  if (!space) {
    return Response.json({ error: "Space not found or access denied" }, { status: 404 });
  }

  const url = new URL(req.url);
  const filePath = url.searchParams.get("path");

  if (!filePath) {
    return Response.json({ error: "path query parameter is required" }, { status: 400 });
  }

  const fileRow = await env.TOSS_DB
    .prepare("SELECT * FROM space_files WHERE space_id = ? AND path = ?")
    .bind(space.id, filePath)
    .first<SpaceFileRow>();

  if (!fileRow) {
    return Response.json({ error: "File not found" }, { status: 404 });
  }

  const object = await downloadFromR2(env.TOSS_STORAGE, fileRow.r2_key);
  if (!object) {
    return Response.json({ error: "File not found in storage" }, { status: 404 });
  }

  const filename = filePath.split("/").pop() || "file";

  return new Response(object.body, {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Length": fileRow.size_bytes.toString(),
    },
  });
}
