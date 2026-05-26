import { type NextRequest, NextResponse } from 'next/server';
import { env } from './env';

const ALLOW_ORIGINS = [
  env.SITE_URL,
  'http://localhost:3000',
  // Extension can call from chrome-extension:// origin; that's checked via token
];

export function corsHeaders(origin: string | null): Headers {
  const headers = new Headers();
  const allowOrigin = origin && ALLOW_ORIGINS.includes(origin) ? origin : env.SITE_URL;
  headers.set('Access-Control-Allow-Origin', origin?.startsWith('chrome-extension://') ? origin : allowOrigin);
  headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  headers.set(
    'Access-Control-Allow-Headers',
    'Content-Type, Authorization, X-Worker-Token, X-Worker-Id'
  );
  headers.set('Access-Control-Max-Age', '86400');
  return headers;
}

export function preflight(req: NextRequest) {
  if (req.method !== 'OPTIONS') return null;
  return new NextResponse(null, { headers: corsHeaders(req.headers.get('origin')) });
}

export function requireWorker(req: NextRequest) {
  const token =
    req.headers.get('x-worker-token') ??
    req.headers.get('authorization')?.replace(/^Bearer\s+/i, '') ??
    '';
  if (!token || token !== env.WORKER_TOKEN) {
    return NextResponse.json(
      { error: 'Invalid worker token' },
      { status: 401, headers: corsHeaders(req.headers.get('origin')) }
    );
  }
  return null;
}

export function workerId(req: NextRequest): string {
  return (req.headers.get('x-worker-id') ?? 'default').slice(0, 64);
}

export function jsonWithCors(req: NextRequest, body: unknown, init?: ResponseInit) {
  const headers = corsHeaders(req.headers.get('origin'));
  if (init?.headers) {
    new Headers(init.headers).forEach((v, k) => headers.set(k, v));
  }
  return NextResponse.json(body, { ...init, headers });
}
