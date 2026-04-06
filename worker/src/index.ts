/**
 * Toss Worker entry point.
 */

import { extractBearerToken, verifyJWT } from "./middleware/auth";
import { addCORSHeaders, handleCORS } from "./middleware/cors";
import { checkRateLimit } from "./middleware/ratelimit";
import { matchRoute } from "./router";
import type { Env } from "./types";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Handle CORS preflight
    const corsResponse = handleCORS(request);
    if (corsResponse) return corsResponse;

    // Match route
    const matched = matchRoute(request.method, request.url);
    if (!matched) {
      return addCORSHeaders(
        Response.json({ error: "Not found" }, { status: 404 }),
      );
    }

    const { route, params } = matched;

    // Auth check
    let userId: string | undefined;
    if (route.requiresAuth) {
      const token = extractBearerToken(request);
      if (!token) {
        return addCORSHeaders(
          Response.json({ error: "Authorization required" }, { status: 401 }),
        );
      }

      const payload = await verifyJWT(token, env);
      if (!payload) {
        return addCORSHeaders(
          Response.json({ error: "Invalid or expired token" }, { status: 401 }),
        );
      }

      userId = payload.sub;

      // Rate limiting (applied to authenticated requests only)
      const rateResult = await checkRateLimit(env, userId);
      if (!rateResult.allowed) {
        return addCORSHeaders(
          new Response(
            JSON.stringify({ error: "Rate limited. Please wait a moment and try again." }),
            {
              status: 429,
              headers: {
                "Content-Type": "application/json",
                "X-RateLimit-Remaining": "0",
              },
            },
          ),
        );
      }
    }

    // Execute handler
    try {
      const response = await route.handler(request, env, params, userId);
      const finalResponse = addCORSHeaders(response);
      return finalResponse;
    } catch (e) {
      console.error("Handler error:", e);
      return addCORSHeaders(
        Response.json({ error: "Internal server error" }, { status: 500 }),
      );
    }
  },

  async scheduled(_event: ScheduledEvent, env: Env, _ctx: ExecutionContext): Promise<void> {
    // Clean up expired documents (older than 30 days, still pending)
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    const expired = await env.TOSS_DB.prepare(
      `SELECT id, r2_key FROM documents WHERE created_at < ? AND status = 'pending'`,
    ).bind(thirtyDaysAgo).all();

    for (const doc of expired.results) {
      await env.TOSS_STORAGE.delete(doc.r2_key as string);
      await env.TOSS_DB.prepare(
        `UPDATE documents SET status = 'expired' WHERE id = ?`,
      ).bind(doc.id).run();
    }

    console.log(`Cleanup: expired ${expired.results.length} documents`);
  },
} satisfies ExportedHandler<Env>;
