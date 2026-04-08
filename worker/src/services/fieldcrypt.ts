/**
 * T1-5: envelope encryption for sensitive D1 text fields.
 *
 * Threat model this layer addresses:
 *   - D1 backup or export is stolen (dump, snapshot, SQLite file leak).
 *   - A read replica / logs leak row values.
 *
 * Threat model this layer DOES NOT address:
 *   - A malicious Worker operator with access to both D1 and the
 *     `D1_ENCRYPTION_KEY` secret.
 *   - Metadata (sender_id / recipient_id / filename / size / timestamps).
 *
 * For those you need Tier 2 (client-side E2E encryption).
 *
 * Ciphertext format (base64url of the concatenation):
 *     version_byte (1)  = 0x01
 *     nonce         (12 bytes, AES-GCM)
 *     ciphertext+tag (N bytes)
 *
 * Serialized with the prefix `enc:v1:` so decrypt can recognise its own
 * output and so plaintext / legacy rows can coexist in the same column.
 */

const PREFIX = "enc:v1:";
const VERSION = 0x01;
const NONCE_LEN = 12; // AES-GCM standard

let cachedKey: CryptoKey | null = null;

async function importKeyFromSecret(secretB64: string): Promise<CryptoKey> {
  if (cachedKey) return cachedKey;
  const raw = base64UrlDecodeBinary(secretB64);
  if (raw.length !== 32) {
    throw new Error(
      `D1_ENCRYPTION_KEY must decode to 32 bytes (got ${raw.length}). ` +
        "Generate with: openssl rand -base64 32 | tr -d '=' | tr '+/' '-_'",
    );
  }
  cachedKey = await crypto.subtle.importKey(
    "raw",
    raw,
    { name: "AES-GCM" },
    false,
    ["encrypt", "decrypt"],
  );
  return cachedKey;
}

/**
 * Encrypt `plaintext`. Returns the opaque `enc:v1:...` string ready to store.
 *
 * Pass-through rules:
 *   - `null` / `undefined` → `null` (caller writes SQL NULL)
 *   - empty string → empty string (pointless to encrypt "")
 *
 * If `D1_ENCRYPTION_KEY` is not configured we log once and return the
 * plaintext unchanged. This keeps the worker working in dev without forcing
 * every contributor to provision a secret just to push a document.
 */
export async function encryptField(
  plaintext: string | null | undefined,
  keySecret: string | undefined,
): Promise<string | null> {
  if (plaintext === null || plaintext === undefined) return null;
  if (plaintext.length === 0) return "";
  if (!keySecret) {
    warnOnceMissingKey();
    return plaintext;
  }

  const key = await importKeyFromSecret(keySecret);
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_LEN));
  const plaintextBytes = new TextEncoder().encode(plaintext);
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, plaintextBytes),
  );

  const packed = new Uint8Array(1 + NONCE_LEN + ciphertext.byteLength);
  packed[0] = VERSION;
  packed.set(nonce, 1);
  packed.set(ciphertext, 1 + NONCE_LEN);

  return PREFIX + base64UrlEncodeBinary(packed);
}

/**
 * Decrypt a value previously produced by `encryptField`. Accepts:
 *   - `null` / `undefined` → `null`
 *   - plaintext without prefix → returned unchanged (legacy row)
 *   - `enc:v1:...` → decrypted and returned
 *
 * On failure (wrong key, tampered ciphertext, unknown version) throws —
 * callers should surface that as a server error, not silently drop data.
 */
export async function decryptField(
  value: string | null | undefined,
  keySecret: string | undefined,
): Promise<string | null> {
  if (value === null || value === undefined) return null;
  if (!value.startsWith(PREFIX)) return value; // legacy plaintext
  if (!keySecret) {
    throw new Error(
      "Row is encrypted (enc:v1:) but D1_ENCRYPTION_KEY is not configured",
    );
  }

  const packed = base64UrlDecodeBinary(value.slice(PREFIX.length));
  if (packed.length <= 1 + NONCE_LEN) {
    throw new Error("Encrypted field too short");
  }
  if (packed[0] !== VERSION) {
    throw new Error(`Unsupported fieldcrypt version: ${packed[0]}`);
  }
  const nonce = packed.slice(1, 1 + NONCE_LEN);
  const ciphertext = packed.slice(1 + NONCE_LEN);

  const key = await importKeyFromSecret(keySecret);
  const plaintextBytes = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce },
    key,
    ciphertext,
  );
  return new TextDecoder().decode(plaintextBytes);
}

/**
 * Convenience: decrypt many rows in parallel. Used on list endpoints so we
 * don't `await` sequentially inside a loop.
 */
export async function decryptFields(
  values: (string | null | undefined)[],
  keySecret: string | undefined,
): Promise<(string | null)[]> {
  return Promise.all(values.map((v) => decryptField(v, keySecret)));
}

let loggedMissingKey = false;
function warnOnceMissingKey(): void {
  if (loggedMissingKey) return;
  loggedMissingKey = true;
  console.warn(
    "[fieldcrypt] D1_ENCRYPTION_KEY not configured; storing sensitive fields in plaintext. " +
      "Generate and set via `wrangler secret put D1_ENCRYPTION_KEY` for production.",
  );
}

function base64UrlEncodeBinary(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecodeBinary(str: string): Uint8Array {
  const padded = str.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
