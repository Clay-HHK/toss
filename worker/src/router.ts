/**
 * Route definitions and dispatcher.
 */

import { handleDeviceFlow, handleDeviceToken, handlePATAuth, handleMe } from "./handlers/auth";
import {
  handleListContacts,
  handleAddContact,
  handleDeleteContact,
  handleResolveContact,
} from "./handlers/contacts";
import {
  handlePushDocument,
  handleListInbox,
  handleDownloadDocument,
  handleListSent,
} from "./handlers/documents";
import type { Env, Route, RouteHandler } from "./types";

function route(
  method: string,
  path: string,
  handler: RouteHandler,
  requiresAuth: boolean = true,
): Route {
  return {
    method,
    pattern: new URLPattern({ pathname: path }),
    handler,
    requiresAuth,
  };
}

export const routes: Route[] = [
  // Auth (no auth required)
  route("POST", "/api/v1/auth/github/device", handleDeviceFlow, false),
  route("POST", "/api/v1/auth/github/token", handleDeviceToken, false),
  route("POST", "/api/v1/auth/pat", handlePATAuth, false),
  route("GET", "/api/v1/auth/me", handleMe),

  // Contacts
  route("GET", "/api/v1/contacts", handleListContacts),
  route("POST", "/api/v1/contacts", handleAddContact),
  route("DELETE", "/api/v1/contacts/:alias", handleDeleteContact),
  route("GET", "/api/v1/contacts/resolve/:name", handleResolveContact),

  // Documents
  route("POST", "/api/v1/documents/push", handlePushDocument),
  route("GET", "/api/v1/documents/inbox", handleListInbox),
  route("GET", "/api/v1/documents/inbox/:id/download", handleDownloadDocument),
  route("GET", "/api/v1/documents/sent", handleListSent),

  // Health check
  route("GET", "/api/v1/health", async () => {
    return Response.json({ status: "ok", version: "0.1.0" });
  }, false),
];

export function matchRoute(
  method: string,
  url: string,
): { route: Route; params: Record<string, string> } | null {
  for (const r of routes) {
    if (r.method !== method) continue;
    const match = r.pattern.exec(url);
    if (match) {
      const params: Record<string, string> = {};
      for (const [key, value] of Object.entries(match.pathname.groups)) {
        if (value !== undefined) params[key] = value;
      }
      return { route: r, params };
    }
  }
  return null;
}
