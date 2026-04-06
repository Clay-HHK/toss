/**
 * Toss Worker entry point.
 */

import { extractBearerToken, verifyJWT } from "./middleware/auth";
import { addCORSHeaders, handleCORS } from "./middleware/cors";
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
    }

    // Execute handler
    try {
      const response = await route.handler(request, env, params, userId);
      return addCORSHeaders(response);
    } catch (e) {
      console.error("Handler error:", e);
      return addCORSHeaders(
        Response.json({ error: "Internal server error" }, { status: 500 }),
      );
    }
  },
} satisfies ExportedHandler<Env>;
