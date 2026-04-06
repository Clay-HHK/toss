/**
 * D1 database query helpers.
 */

import type { Env, UserRow } from "../types";

export async function findUserByGitHubId(
  db: D1Database,
  githubId: number,
): Promise<UserRow | null> {
  return db
    .prepare("SELECT * FROM users WHERE github_id = ?")
    .bind(githubId)
    .first<UserRow>();
}

export async function findUserByGitHubUsername(
  db: D1Database,
  username: string,
): Promise<UserRow | null> {
  return db
    .prepare("SELECT * FROM users WHERE github_username = ?")
    .bind(username)
    .first<UserRow>();
}

export async function findUserById(
  db: D1Database,
  id: string,
): Promise<UserRow | null> {
  return db
    .prepare("SELECT * FROM users WHERE id = ?")
    .bind(id)
    .first<UserRow>();
}

export async function upsertUser(
  db: D1Database,
  id: string,
  githubUsername: string,
  githubId: number,
  displayName: string | null,
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO users (id, github_username, github_id, display_name)
       VALUES (?, ?, ?, ?)
       ON CONFLICT (github_id) DO UPDATE SET
         github_username = excluded.github_username,
         display_name = excluded.display_name,
         last_seen_at = datetime('now')`,
    )
    .bind(id, githubUsername, githubId, displayName)
    .run();
}

export async function updateLastSeen(db: D1Database, userId: string): Promise<void> {
  await db
    .prepare("UPDATE users SET last_seen_at = datetime('now') WHERE id = ?")
    .bind(userId)
    .run();
}
