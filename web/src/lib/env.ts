/**
 * Centralised env access. Throws clearly when a required var is missing
 * so deployment misconfigurations fail fast instead of at runtime.
 */
function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

function optional(name: string, fallback = ''): string {
  return process.env[name] ?? fallback;
}

export const env = {
  MONGODB_URI: required('MONGODB_URI'),
  MONGODB_DB: optional('MONGODB_DB', 'bulk_gpt'),
  SESSION_SECRET: required('SESSION_SECRET'),
  WORKER_TOKEN: required('WORKER_TOKEN'),
  ADMIN_MASTER_KEY: required('ADMIN_MASTER_KEY'),
  SITE_URL: optional('NEXT_PUBLIC_SITE_URL', 'http://localhost:3000'),
};
