import { getIronSession, type SessionOptions } from 'iron-session';
import { cookies } from 'next/headers';
import { env } from './env';

export interface SessionData {
  keyId?: string; // mongo _id as string
  key?: string;
  planName?: string;
  isAdmin?: boolean;
}

const sessionOptions: SessionOptions = {
  password: env.SESSION_SECRET,
  cookieName: 'bgt_session',
  cookieOptions: {
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    httpOnly: true,
    path: '/',
    maxAge: 60 * 60 * 24 * 30, // 30 days
  },
};

export async function getSession() {
  return getIronSession<SessionData>(await cookies(), sessionOptions);
}
