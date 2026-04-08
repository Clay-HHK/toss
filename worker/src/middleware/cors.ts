/**
 * CORS + strict security headers for the Toss API.
 *
 * T1-6: every response that flows through `addCORSHeaders` is hardened with
 * HSTS / CSP / X-Frame-Options / Referrer-Policy / Permissions-Policy and
 * `nosniff`. Blob responses set their own `Content-Type` and rely on the same
 * pipeline to add the rest of the headers.
 */

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Authorization, X-Content-SHA256, X-Toss-Device-Id, X-Toss-Client-Version",
  "Access-Control-Expose-Headers":
    "X-Content-SHA256, X-Toss-Encryption, X-Deprecated, Content-Disposition",
  "Access-Control-Max-Age": "86400",
};

const SECURITY_HEADERS: Record<string, string> = {
  // Force HTTPS for one year and pre-include subdomains for the worker host.
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  // Reject content-type sniffing — uploads are stored verbatim.
  "X-Content-Type-Options": "nosniff",
  // No reason to ever frame the API.
  "X-Frame-Options": "DENY",
  // Don't leak the API host to third parties.
  "Referrer-Policy": "no-referrer",
  // Lock down ambient browser features just in case the API is loaded as a doc.
  "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
  // The API only ever serves JSON or opaque blobs; deny everything else.
  "Content-Security-Policy":
    "default-src 'none'; frame-ancestors 'none'; sandbox; base-uri 'none'; form-action 'none'",
  // Hide implementation details from response inspectors.
  "X-Toss-Server": "toss-worker",
};

function applyHeaders(response: Response): Response {
  const out = new Response(response.body, response);
  for (const [key, value] of Object.entries(CORS_HEADERS)) {
    out.headers.set(key, value);
  }
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    // Only set if not already present so handlers can opt-out (e.g. richer CSP
    // for blob downloads if we ever need it).
    if (!out.headers.has(key)) {
      out.headers.set(key, value);
    }
  }
  return out;
}

export function handleCORS(request: Request): Response | null {
  if (request.method === "OPTIONS") {
    const headers: Record<string, string> = { ...CORS_HEADERS, ...SECURITY_HEADERS };
    return new Response(null, { status: 204, headers });
  }
  return null;
}

export function addCORSHeaders(response: Response): Response {
  return applyHeaders(response);
}
