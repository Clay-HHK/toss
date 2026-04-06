/**
 * Group management handlers.
 */

import { uploadToR2 } from "../services/storage";
import type { Env, GroupRow } from "../types";

function generateInviteCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const parts = [0, 0].map(() => {
    let s = "";
    for (let i = 0; i < 4; i++) {
      s += chars[Math.floor(Math.random() * chars.length)];
    }
    return s;
  });
  return parts.join("-");
}

/**
 * POST /api/v1/groups
 * Body: { name, slug? }
 */
export async function handleCreateGroup(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const body = await req.json<{ name: string; slug?: string }>();
  if (!body.name) {
    return Response.json({ error: "name is required" }, { status: 400 });
  }

  const slug = (body.slug || body.name)
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  if (!slug) {
    return Response.json({ error: "Invalid slug" }, { status: 400 });
  }

  const id = crypto.randomUUID();
  const inviteCode = generateInviteCode();

  try {
    await env.TOSS_DB
      .prepare(
        `INSERT INTO groups (id, name, slug, invite_code, owner_id) VALUES (?, ?, ?, ?, ?)`,
      )
      .bind(id, body.name, slug, inviteCode, userId!)
      .run();

    // Owner is automatically a member
    await env.TOSS_DB
      .prepare(`INSERT INTO group_members (group_id, user_id) VALUES (?, ?)`)
      .bind(id, userId!)
      .run();
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes("UNIQUE")) {
      return Response.json(
        { error: `Group slug "${slug}" already exists` },
        { status: 409 },
      );
    }
    throw e;
  }

  return Response.json(
    { id, name: body.name, slug, invite_code: inviteCode },
    { status: 201 },
  );
}

/**
 * GET /api/v1/groups
 */
export async function handleListGroups(
  _req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const rows = await env.TOSS_DB
    .prepare(
      `SELECT g.id, g.name, g.slug, g.invite_code, g.owner_id, g.created_at,
              (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.id) as member_count
       FROM groups g
       JOIN group_members gm ON g.id = gm.group_id
       WHERE gm.user_id = ?
       ORDER BY g.created_at DESC`,
    )
    .bind(userId!)
    .all();

  return Response.json({ groups: rows.results });
}

/**
 * GET /api/v1/groups/:slug/invite
 */
export async function handleGetInvite(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const group = await env.TOSS_DB
    .prepare("SELECT * FROM groups WHERE slug = ? AND owner_id = ?")
    .bind(params.slug, userId!)
    .first<GroupRow>();

  if (!group) {
    return Response.json(
      { error: "Group not found or you are not the owner" },
      { status: 404 },
    );
  }

  return Response.json({
    invite_code: group.invite_code,
    group_name: group.name,
    slug: group.slug,
  });
}

/**
 * POST /api/v1/groups/join
 * Body: { invite_code }
 */
export async function handleJoinGroup(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const body = await req.json<{ invite_code: string }>();
  if (!body.invite_code) {
    return Response.json({ error: "invite_code is required" }, { status: 400 });
  }

  const group = await env.TOSS_DB
    .prepare("SELECT * FROM groups WHERE invite_code = ?")
    .bind(body.invite_code)
    .first<GroupRow>();

  if (!group) {
    return Response.json({ error: "Invalid invite code" }, { status: 404 });
  }

  // Check if already a member
  const existing = await env.TOSS_DB
    .prepare("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?")
    .bind(group.id, userId!)
    .first();

  if (existing) {
    return Response.json({ message: "Already a member", group_name: group.name, slug: group.slug });
  }

  await env.TOSS_DB
    .prepare("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)")
    .bind(group.id, userId!)
    .run();

  return Response.json({ message: "Joined", group_name: group.name, slug: group.slug });
}

/**
 * GET /api/v1/groups/:slug/members
 */
export async function handleListMembers(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  // Verify membership
  const group = await verifyGroupMembership(env, params.slug, userId!);
  if (!group) {
    return Response.json({ error: "Group not found or not a member" }, { status: 404 });
  }

  const rows = await env.TOSS_DB
    .prepare(
      `SELECT u.github_username, u.display_name, gm.joined_at,
              CASE WHEN g.owner_id = u.id THEN 'owner' ELSE 'member' END as role
       FROM group_members gm
       JOIN users u ON gm.user_id = u.id
       JOIN groups g ON gm.group_id = g.id
       WHERE gm.group_id = ?
       ORDER BY gm.joined_at`,
    )
    .bind(group.id)
    .all();

  return Response.json({ members: rows.results, group_name: group.name });
}

/**
 * POST /api/v1/groups/:slug/push
 * Multipart form: file, message (optional)
 * Pushes to ALL members except the sender.
 */
export async function handleGroupPush(
  req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const group = await verifyGroupMembership(env, params.slug, userId!);
  if (!group) {
    return Response.json({ error: "Group not found or not a member" }, { status: 404 });
  }

  const formData = await req.formData();
  const file = formData.get("file") as File | null;
  const message = formData.get("message") as string | null;

  if (!file) {
    return Response.json({ error: "file is required" }, { status: 400 });
  }

  const MAX_FILE_SIZE = 50 * 1024 * 1024;
  if (file.size > MAX_FILE_SIZE) {
    return Response.json(
      { error: "File too large", detail: "Maximum file size is 50MB" },
      { status: 413 },
    );
  }

  // Get all members except sender
  const members = await env.TOSS_DB
    .prepare(
      `SELECT gm.user_id FROM group_members gm WHERE gm.group_id = ? AND gm.user_id != ?`,
    )
    .bind(group.id, userId!)
    .all<{ user_id: string }>();

  if (members.results.length === 0) {
    return Response.json({ error: "No other members in this group" }, { status: 400 });
  }

  const fileBytes = await file.arrayBuffer();
  const contentType = file.type || "application/octet-stream";
  const groupMsg = message ? `[${group.name}] ${message}` : `[${group.name}]`;

  const delivered: string[] = [];

  for (const member of members.results) {
    const docId = crypto.randomUUID();
    const r2Key = `documents/inbox/${member.user_id}/${docId}/${file.name}`;

    await uploadToR2(env.TOSS_STORAGE, r2Key, fileBytes, contentType);

    await env.TOSS_DB
      .prepare(
        `INSERT INTO documents (id, sender_id, recipient_id, filename, r2_key, size_bytes, content_type, message)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(docId, userId!, member.user_id, file.name, r2Key, fileBytes.byteLength, contentType, groupMsg)
      .run();

    delivered.push(member.user_id);
  }

  return Response.json({
    filename: file.name,
    group: group.name,
    delivered_count: delivered.length,
    size_bytes: fileBytes.byteLength,
    status: "delivered",
  }, { status: 201 });
}

async function verifyGroupMembership(
  env: Env,
  slug: string,
  userId: string,
): Promise<GroupRow | null> {
  const group = await env.TOSS_DB
    .prepare("SELECT * FROM groups WHERE slug = ?")
    .bind(slug)
    .first<GroupRow>();

  if (!group) return null;

  const member = await env.TOSS_DB
    .prepare("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?")
    .bind(group.id, userId)
    .first();

  return member ? group : null;
}
