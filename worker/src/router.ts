/**
 * Route definitions and dispatcher.
 */

import {
  handleDeviceFlow,
  handleDeviceToken,
  handlePATAuth,
  handleMe,
  handleRevokeToken,
} from "./handlers/auth";
import { handleRedeemBlobTicket } from "./handlers/blobs";
import { handleCleanupExpired } from "./handlers/cleanup";
import { handleMigrateR2Keys } from "./handlers/migrate";
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
  handleMintDocumentTicket,
  handlePreviewDocument,
  handleDeleteDocument,
  handleListSent,
} from "./handlers/documents";
import {
  handleCreateGroup,
  handleListGroups,
  handleGetInvite,
  handleJoinGroup,
  handleListMembers,
  handleGroupPush,
} from "./handlers/groups";
import {
  handleCreateSpace,
  handleListSpaces,
  handleAddMember,
  handleSyncSpace,
  handleUploadSpaceFile,
  handleDownloadSpaceFile,
  handleMintSpaceFileTicket,
} from "./handlers/spaces";
import type { Route, RouteHandler } from "./types";

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
  // T1-4: revoke the JWT used to call this endpoint (a.k.a. logout).
  route("POST", "/api/v1/auth/revoke", handleRevokeToken),

  // Contacts
  route("GET", "/api/v1/contacts", handleListContacts),
  route("POST", "/api/v1/contacts", handleAddContact),
  route("DELETE", "/api/v1/contacts/:alias", handleDeleteContact),
  route("GET", "/api/v1/contacts/resolve/:name", handleResolveContact),

  // Documents
  route("POST", "/api/v1/documents/push", handlePushDocument),
  route("GET", "/api/v1/documents/inbox", handleListInbox),
  // T1-2: mint a short-lived download ticket (preferred path for new clients).
  route("POST", "/api/v1/documents/inbox/:id/ticket", handleMintDocumentTicket),
  // Legacy direct-download path kept for backward compat. Will be removed
  // once clients have rolled over to the ticket flow.
  route("GET", "/api/v1/documents/inbox/:id/download", handleDownloadDocument),
  route("GET", "/api/v1/documents/inbox/:id/preview", handlePreviewDocument),
  route("DELETE", "/api/v1/documents/inbox/:id", handleDeleteDocument),
  route("GET", "/api/v1/documents/sent", handleListSent),

  // T1-2: blob redemption endpoint (no auth; the ticket is the proof).
  route("GET", "/api/v1/blobs/:ticket", handleRedeemBlobTicket, false),

  // Spaces
  route("POST", "/api/v1/spaces", handleCreateSpace),
  route("GET", "/api/v1/spaces", handleListSpaces),
  route("POST", "/api/v1/spaces/:slug/members", handleAddMember),
  route("POST", "/api/v1/spaces/:slug/sync", handleSyncSpace),
  route("POST", "/api/v1/spaces/:slug/files/upload", handleUploadSpaceFile),
  route("POST", "/api/v1/spaces/:slug/files/ticket", handleMintSpaceFileTicket),
  route("GET", "/api/v1/spaces/:slug/files/download", handleDownloadSpaceFile),

  // Groups
  route("POST", "/api/v1/groups", handleCreateGroup),
  route("GET", "/api/v1/groups", handleListGroups),
  route("POST", "/api/v1/groups/join", handleJoinGroup),
  route("GET", "/api/v1/groups/:slug/invite", handleGetInvite),
  route("GET", "/api/v1/groups/:slug/members", handleListMembers),
  route("POST", "/api/v1/groups/:slug/push", handleGroupPush),

  // Admin
  route("POST", "/api/v1/admin/cleanup", handleCleanupExpired),
  // T1-1 one-shot migration: rename legacy r2_key rows to opaque blobs/ keys.
  // Gated by X-Migration-Secret header (env MIGRATION_SECRET); no JWT required.
  route("POST", "/api/v1/admin/migrate/r2-keys", handleMigrateR2Keys, false),

  // Health check + capability advertisement (T1-7).
  // Clients call this once at startup to discover which security features
  // the server supports, then choose the best path (e.g. ticket vs. legacy
  // download, encrypted vs. plaintext upload).
  route("GET", "/api/v1/health", async () => {
    return Response.json({
      status: "ok",
      version: "0.2.0",
      features: SERVER_FEATURES,
    });
  }, false),
];

/**
 * Capability flags exposed via /api/v1/health.
 *
 * Add a flag here when shipping a new server-side feature so clients can probe
 * for it instead of hard-coding version comparisons.
 */
export const SERVER_FEATURES: readonly string[] = [
  "content-sha256", // T1-3: server stores + echoes X-Content-SHA256
  "strict-headers", // T1-6: HSTS / CSP / X-Frame-Options on every response
  "opaque-blob-keys", // T1-1: R2 object keys carry no recipient or filename
  "download-ticket", // T1-2: short-lived download tickets via /api/v1/blobs/:ticket
  "device-bound-jwt", // T1-4: JWT carries jti+dev; /api/v1/auth/revoke blacklists jti
  "field-encryption", // T1-5: documents.message stored via AES-GCM envelope
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
