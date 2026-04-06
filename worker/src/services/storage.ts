/**
 * R2 object storage abstraction.
 */

export async function uploadToR2(
  bucket: R2Bucket,
  key: string,
  body: ReadableStream | ArrayBuffer | string,
  contentType: string = "application/octet-stream",
): Promise<R2Object> {
  return bucket.put(key, body, {
    httpMetadata: { contentType },
  });
}

export async function downloadFromR2(
  bucket: R2Bucket,
  key: string,
): Promise<R2ObjectBody | null> {
  return bucket.get(key);
}

export async function deleteFromR2(
  bucket: R2Bucket,
  key: string,
): Promise<void> {
  await bucket.delete(key);
}

export async function listR2Objects(
  bucket: R2Bucket,
  prefix: string,
): Promise<R2Objects> {
  return bucket.list({ prefix });
}
