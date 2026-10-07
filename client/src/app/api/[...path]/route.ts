import { NextRequest, NextResponse } from 'next/server';

function getCandidateApis(): string[] {
  // Compose supplies the service URL; local development uses the published port.
  // Replaying writes against guessed hosts can duplicate account/order creation.
  return [(process.env.API_URL || 'http://127.0.0.1:8000/api/v1').trim().replace(/\/$/, '')];
}

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

  const candidateApis = getCandidateApis();
  let upstream: Response | undefined;
  let activeApi = candidateApis[0];
  let lastError: unknown;

  try {
    for (const baseApi of candidateApis) {
      const url = `${baseApi}/${route}/${request.nextUrl.search}`;
      const payload = typeof body === 'string' ? body : body ? body.slice(0) : undefined;
      try {
        upstream = await fetch(url, {
          method: request.method,
          body: payload,
          headers,
          cache: 'no-store',
          signal: route === 'notifications/stream' ? AbortSignal.any([request.signal, AbortSignal.timeout(35000)]) : AbortSignal.timeout(10000),
        });
        activeApi = baseApi;
        break;
      } catch (err) {
        lastError = err;
      }
    }

    if (!upstream) {
      throw lastError || new Error('All candidate backend APIs failed to respond.');
    }

    let newAccess: string | undefined;
    if (upstream.status === 401 && refresh && !route.startsWith('auth/')) {
      const renewed = await fetch(`${activeApi}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
        cache: 'no-store',
        signal: route === 'notifications/stream' ? AbortSignal.any([request.signal, AbortSignal.timeout(35000)]) : AbortSignal.timeout(10000),
      });
      if (renewed.ok) {
        newAccess = (await renewed.json()).access;
        headers.Authorization = `Bearer ${newAccess}`;
        const url = `${activeApi}/${route}/${request.nextUrl.search}`;
        const payload = typeof body === 'string' ? body : body ? body.slice(0) : undefined;
        upstream = await fetch(url, {
          method: request.method,
          body: payload,
          headers,
          cache: 'no-store',
          signal: (route === 'notifications/stream' || route.includes('digital-asset')) ? AbortSignal.any([request.signal, AbortSignal.timeout(300000)]) : AbortSignal.timeout(10000),
        });
      }
    }
    if (route === 'notifications/stream' && upstream.ok && upstream.body) {
      const response = new NextResponse(upstream.body, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no' } });
      if (newAccess) response.cookies.set('proace_access', newAccess, { ...options, maxAge: 900 });
      return response;
    }
    const upstreamType = upstream.headers.get('content-type') || '';
    if (upstream.ok && !upstreamType.includes('application/json')) {
      const response = new NextResponse(upstream.body, {
        status: upstream.status,
        headers: {
          'Content-Type': upstreamType || 'application/octet-stream',
          'Content-Disposition': upstream.headers.get('content-disposition') || 'inline',
          'Cache-Control': 'private, no-store',
        },
      });
      if (newAccess) response.cookies.set('proace_access', newAccess, { ...options, maxAge: 900 });
      return response;
    }
    const data = upstream.status === 204 ? null : await upstream.json().catch(() => ({ detail: 'The server could not process this request.' }));
    const loginTokens = ['auth/login', 'password/change'].includes(route) && upstream.ok ? { access: data.access, refresh: data.refresh } : null;
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
  } catch (error) {
    console.error(`[API Proxy Error] Failed to proxy ${request.method} /api/${route}:`, error);
    if (route === 'auth/logout') {
      const response = NextResponse.json(null);
      response.cookies.delete('proace_access'); response.cookies.delete('proace_refresh');
      return response;
    }
    const detail = 'The server is temporarily unavailable. Please try again shortly.';
    return NextResponse.json({ detail }, { status: 503 });
  }
}

export { handler as GET, handler as POST, handler as PATCH, handler as PUT, handler as DELETE };
