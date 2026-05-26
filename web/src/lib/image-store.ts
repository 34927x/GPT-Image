import type { ObjectId } from 'mongodb';
import { env, isCloudinaryConfigured } from './env';

interface UploadInput {
  dataUrl: string;
  keyId: ObjectId;
  prompt: string;
}

interface UploadResult {
  url: string;
  storage: 'cloudinary' | 'mongodb';
}

/**
 * Stores an image returned from the worker. If Cloudinary creds are present,
 * uploads there and returns a CDN URL. Otherwise falls back to a data URL
 * (kept inline; fine for low volume, not for production scale).
 *
 * For Cloudinary uploads we use the unsigned upload preset path with a SHA-1
 * signature to avoid pulling in their SDK.
 */
export async function uploadImage(input: UploadInput): Promise<UploadResult> {
  if (!isCloudinaryConfigured()) {
    return { url: input.dataUrl, storage: 'mongodb' };
  }

  const timestamp = Math.floor(Date.now() / 1000);
  const folder = `bulk-gpt/${input.keyId.toString()}`;

  // Build sorted params -> sha1(<params>API_SECRET)
  const params = `folder=${folder}&timestamp=${timestamp}`;
  const signature = await sha1(params + env.CLOUDINARY.API_SECRET);

  const form = new FormData();
  form.append('file', input.dataUrl);
  form.append('api_key', env.CLOUDINARY.API_KEY);
  form.append('timestamp', String(timestamp));
  form.append('folder', folder);
  form.append('signature', signature);

  const res = await fetch(
    `https://api.cloudinary.com/v1_1/${env.CLOUDINARY.CLOUD_NAME}/image/upload`,
    { method: 'POST', body: form }
  );

  if (!res.ok) {
    // Fall back to base64 if upload fails (bad creds, network etc).
    return { url: input.dataUrl, storage: 'mongodb' };
  }

  const data = (await res.json()) as { secure_url?: string };
  if (!data.secure_url) return { url: input.dataUrl, storage: 'mongodb' };

  return { url: data.secure_url, storage: 'cloudinary' };
}

async function sha1(input: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
