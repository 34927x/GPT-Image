import { NextResponse, type NextRequest } from 'next/server';

/**
 * We do session checks server-side in layouts (which redirect when needed)
 * since iron-session needs to read & decrypt the cookie. The middleware just
 * sets security headers and adds a small per-route shortcut: if there's no
 * session cookie at all, bounce protected routes to /login without doing
 * a Mongo round-trip.
 */
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const protectedPaths = ['/dashboard', '/admin'];
  const isProtected = protectedPaths.some((p) => pathname.startsWith(p));

  if (isProtected && !req.cookies.get('bgt_session')) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }

  const res = NextResponse.next();
  res.headers.set('X-Frame-Options', 'DENY');
  res.headers.set('X-Content-Type-Options', 'nosniff');
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  return res;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
