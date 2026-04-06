/**
 * Contacts CRUD handlers.
 */

import { findUserByGitHubUsername } from "../services/db";
import type { ContactRow, Env } from "../types";

/**
 * GET /api/v1/contacts
 */
export async function handleListContacts(
  _req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const rows = await env.TOSS_DB
    .prepare(
      `SELECT c.alias, c.target_id, u.github_username, u.display_name
       FROM contacts c
       JOIN users u ON c.target_id = u.id
       WHERE c.owner_id = ?
       ORDER BY c.alias`,
    )
    .bind(userId!)
    .all();

  return Response.json({ contacts: rows.results });
}

/**
 * POST /api/v1/contacts
 * Body: { github_username, alias }
 */
export async function handleAddContact(
  req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const body = await req.json<{ github_username: string; alias: string }>();

  if (!body.github_username || !body.alias) {
    return Response.json(
      { error: "github_username and alias are required" },
      { status: 400 },
    );
  }

  const alias = body.alias.trim().toLowerCase();
  if (!/^[a-z0-9_-]+$/.test(alias)) {
    return Response.json(
      { error: "Alias must contain only lowercase letters, numbers, hyphens, underscores" },
      { status: 400 },
    );
  }

  // Find target user
  const target = await findUserByGitHubUsername(env.TOSS_DB, body.github_username);
  if (!target) {
    return Response.json(
      { error: `User @${body.github_username} not found. They need to run \`toss login\` first.` },
      { status: 404 },
    );
  }

  if (target.id === userId) {
    return Response.json({ error: "Cannot add yourself as a contact" }, { status: 400 });
  }

  // Check for duplicates
  const existing = await env.TOSS_DB
    .prepare("SELECT id FROM contacts WHERE owner_id = ? AND (alias = ? OR target_id = ?)")
    .bind(userId!, alias, target.id)
    .first<ContactRow>();

  if (existing) {
    return Response.json(
      { error: "Contact or alias already exists" },
      { status: 409 },
    );
  }

  const id = crypto.randomUUID();
  await env.TOSS_DB
    .prepare("INSERT INTO contacts (id, owner_id, target_id, alias) VALUES (?, ?, ?, ?)")
    .bind(id, userId!, target.id, alias)
    .run();

  return Response.json({
    id,
    alias,
    github_username: target.github_username,
    display_name: target.display_name,
  }, { status: 201 });
}

/**
 * DELETE /api/v1/contacts/:alias
 */
export async function handleDeleteContact(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const alias = params.alias;

  const result = await env.TOSS_DB
    .prepare("DELETE FROM contacts WHERE owner_id = ? AND alias = ?")
    .bind(userId!, alias)
    .run();

  if (!result.meta.changes) {
    return Response.json({ error: "Contact not found" }, { status: 404 });
  }

  return Response.json({ ok: true });
}

/**
 * GET /api/v1/contacts/resolve/:name
 * Resolve alias or github_username to user_id.
 */
export async function handleResolveContact(
  _req: Request,
  env: Env,
  params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  const name = params.name;

  // Try alias first
  const byAlias = await env.TOSS_DB
    .prepare(
      `SELECT c.target_id as user_id, u.github_username, u.display_name
       FROM contacts c
       JOIN users u ON c.target_id = u.id
       WHERE c.owner_id = ? AND c.alias = ?`,
    )
    .bind(userId!, name)
    .first();

  if (byAlias) {
    return Response.json(byAlias);
  }

  // Fall back to GitHub username lookup
  const byUsername = await findUserByGitHubUsername(env.TOSS_DB, name);
  if (byUsername) {
    return Response.json({
      user_id: byUsername.id,
      github_username: byUsername.github_username,
      display_name: byUsername.display_name,
    });
  }

  return Response.json(
    { error: `No contact or user found for "${name}"` },
    { status: 404 },
  );
}
