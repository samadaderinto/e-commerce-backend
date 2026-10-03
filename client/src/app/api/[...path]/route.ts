import { NextRequest, NextResponse } from 'next/server';

const API = process.env.API_URL || 'http://127.0.0.1:8000/api/v1';

async function handler(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const isSecure = request.nextUrl.protocol === 'https:' || request.headers.get('x-forwarded-proto') === 'https';
  const options = { httpOnly: true, secure: isSecure, sameSite: 'lax' as const, path: '/' };
  const { path } = await params;
  if (path.some(part => !/^[a-zA-Z0-9_-]+$/.test(part))) return NextResponse.json({ detail: 'Invalid route.' }, { status: 400 });
  if (!['GET', 'HEAD'].includes(request.method)) {
    const origin = request.headers.get('origin');
    if (!origin || new URL(origin).host !== request.headers.get('host')) return NextResponse.json({ detail: 'Invalid request origin.' }, { status: 403 });
  }
  const route = path.join('/');
  const access = request.cookies.get('proace_access')?.value;
  const refresh = request.cookies.get('proace_refresh')?.value;
  const headers: Record<string, string> = {};
  if (request.headers.get('content-type')) headers['Content-Type'] = request.headers.get('content-type')!;
  if (access) headers.Authorization = `Bearer ${access}`;
  let body: ArrayBuffer | string | undefined = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();
  if (route === 'auth/logout') { body = JSON.stringify({ refresh }); headers['Content-Type'] = 'application/json'; }
  if (route === 'auth/refresh') return NextResponse.json({ detail: 'Not found.' }, { status: 404 });
  try {
    const url = `${API}/${route}/${request.nextUrl.search}`;
    const run = () => fetch(url, { method: request.method, body, headers, cache: 'no-store', signal: AbortSignal.timeout(20000) });
    let upstream = await run();
    let newAccess: string | undefined;
    if (upstream.status === 401 && refresh && !route.startsWith('auth/')) {
      const renewed = await fetch(`${API}/auth/refresh/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }), cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (renewed.ok) {
        newAccess = (await renewed.json()).access;
        headers.Authorization = `Bearer ${newAccess}`;
        upstream = await run();
      }
    }
    const data = upstream.status === 204 ? null : await upstream.json().catch(() => ({ detail: 'The server could not process this request.' }));
    const loginTokens = route === 'auth/login' && upstream.ok ? { access: data.access, refresh: data.refresh } : null;
    if (loginTokens) { delete data.access; delete data.refresh; }
    const response = NextResponse.json(data, { status: upstream.status === 204 ? 200 : upstream.status, headers: { 'Cache-Control': 'no-store' } });
    if (newAccess) response.cookies.set('proace_access', newAccess, { ...options, maxAge: 900 });
    if (loginTokens) {
      response.cookies.set('proace_access', loginTokens.access, { ...options, maxAge: 900 });
      response.cookies.set('proace_refresh', loginTokens.refresh, { ...options, maxAge: 604800 });
    }
    if (route === 'auth/logout' || (upstream.status === 401 && !route.startsWith('auth/'))) {
      response.cookies.delete('proace_access'); response.cookies.delete('proace_refresh');
    }
    return response;
  } catch {
    if (route === 'auth/logout') {
      const response = NextResponse.json(null);
      response.cookies.delete('proace_access'); response.cookies.delete('proace_refresh');
      return response;
    }
    return NextResponse.json({ detail: 'The shop is temporarily unavailable. Please try again shortly.' }, { status: 503 });
  }
}

export { handler as GET, handler as POST, handler as PATCH, handler as PUT, handler as DELETE };
