/**
 * Authentication handlers: GitHub Device Flow and PAT.
 */

import { signJWT } from "../middleware/auth";
import { findUserByGitHubId, findUserById, upsertUser, updateLastSeen } from "../services/db";
import {
  getGitHubUserByPAT,
  startDeviceFlow,
  exchangeDeviceCode,
} from "../services/github";
import type { Env } from "../types";

/**
 * POST /api/v1/auth/pat
 * Authenticate with a GitHub Personal Access Token.
 */
export async function handlePATAuth(
  req: Request,
  env: Env,
): Promise<Response> {
  const body = await req.json<{ pat: string }>();
  if (!body.pat) {
    return Response.json({ error: "pat is required" }, { status: 400 });
  }

  let ghUser;
  try {
    ghUser = await getGitHubUserByPAT(body.pat);
  } catch {
    return Response.json({ error: "Invalid GitHub token" }, { status: 401 });
  }

  // Upsert user in D1
  let user = await findUserByGitHubId(env.TOSS_DB, ghUser.id);
  const userId = user?.id ?? crypto.randomUUID();

  await upsertUser(env.TOSS_DB, userId, ghUser.login, ghUser.id, ghUser.name);

  // Re-fetch to get final ID (in case of conflict resolution)
  user = await findUserByGitHubId(env.TOSS_DB, ghUser.id);
  const finalId = user!.id;

  const jwt = await signJWT(finalId, ghUser.login, env);

  return Response.json({
    jwt,
    github_username: ghUser.login,
    display_name: ghUser.name,
    user_id: finalId,
  });
}

/**
 * POST /api/v1/auth/github/device
 * Start GitHub OAuth device flow.
 */
export async function handleDeviceFlow(
  _req: Request,
  env: Env,
): Promise<Response> {
  try {
    const result = await startDeviceFlow(env.GITHUB_CLIENT_ID);
    // Store device_code in KV for later verification
    await env.TOSS_KV.put(
      `device:${result.device_code}`,
      JSON.stringify({ status: "pending" }),
      { expirationTtl: result.expires_in },
    );

    return Response.json(result);
  } catch (e) {
    return Response.json(
      { error: `Failed to start device flow: ${e}` },
      { status: 500 },
    );
  }
}

/**
 * POST /api/v1/auth/github/token
 * Exchange device code for JWT (polling endpoint).
 */
export async function handleDeviceToken(
  req: Request,
  env: Env,
): Promise<Response> {
  const body = await req.json<{ device_code: string }>();
  if (!body.device_code) {
    return Response.json({ error: "device_code is required" }, { status: 400 });
  }

  // Exchange with GitHub
  const tokenResp = await exchangeDeviceCode(env.GITHUB_CLIENT_ID, body.device_code);

  if (tokenResp.error) {
    return Response.json({ error: tokenResp.error }, { status: 202 });
  }

  if (!tokenResp.access_token) {
    return Response.json({ error: "authorization_pending" }, { status: 202 });
  }

  // Get GitHub user with the access token
  let ghUser;
  try {
    ghUser = await getGitHubUserByPAT(tokenResp.access_token);
  } catch {
    return Response.json({ error: "Failed to get GitHub user" }, { status: 500 });
  }

  // Upsert user
  let user = await findUserByGitHubId(env.TOSS_DB, ghUser.id);
  const userId = user?.id ?? crypto.randomUUID();
  await upsertUser(env.TOSS_DB, userId, ghUser.login, ghUser.id, ghUser.name);

  user = await findUserByGitHubId(env.TOSS_DB, ghUser.id);
  const finalId = user!.id;

  // Clean up KV
  await env.TOSS_KV.delete(`device:${body.device_code}`);

  const jwt = await signJWT(finalId, ghUser.login, env);

  return Response.json({
    jwt,
    github_username: ghUser.login,
    display_name: ghUser.name,
    user_id: finalId,
  });
}

/**
 * GET /api/v1/auth/me
 * Get current authenticated user info.
 */
export async function handleMe(
  _req: Request,
  env: Env,
  _params: Record<string, string>,
  userId?: string,
): Promise<Response> {
  if (!userId) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = await findUserById(env.TOSS_DB, userId);
  if (!user) {
    return Response.json({ error: "User not found" }, { status: 404 });
  }

  await updateLastSeen(env.TOSS_DB, userId);

  return Response.json({
    id: user.id,
    github_username: user.github_username,
    display_name: user.display_name,
    created_at: user.created_at,
  });
}
