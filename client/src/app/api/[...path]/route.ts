import { NextRequest, NextResponse } from 'next/server';
import { accessCookieMaxAge, refreshOnce } from '@/lib/auth-refresh';
import type { RefreshResult } from '@/lib/auth-refresh';
import { isSameOrigin } from '@/lib/request-origin';
import { proxyDiagnosticHeaders } from '@/lib/proxy-diagnostics';
import { proxyTarget } from '@/lib/proxy-target';

function getCandidateApis(route: string): string[] {
  // Compose supplies the service URL; local development uses the published port.
  // Replaying writes against guessed hosts can duplicate account/order creation.
  return [proxyTarget(route, process.env.API_URL, process.env.NOTIFICATION_STREAM_URL)];
}

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const started: number = performance.now();
  const isSecure =
    request.nextUrl.protocol === 'https:' ||
    request.headers.get('x-forwarded-proto') === 'https';

  const options = {
    httpOnly: true,
    secure: isSecure,
    sameSite: 'lax' as const,
    path: '/',
  };

  function clearAuthCookies(response: NextResponse): void {
    response.cookies.set('proace_access', '', {
      ...options,
      expires: new Date(0),
      maxAge: 0,
    });
    response.cookies.set('proace_refresh', '', {
      ...options,
      expires: new Date(0),
      maxAge: 0,
    });
  }

  const { path } = await params;
  if (path.some((part) => !/^[a-zA-Z0-9_-]+$/.test(part))) {
    return NextResponse.json({ detail: 'Invalid route.' }, { status: 400 });
  }
  const route = path.join('/');
  const paymentWebhook = route === 'checkout/stripe-webhook' || route === 'stripe/webhook';

  if (!['GET', 'HEAD'].includes(request.method) && !paymentWebhook) {
    const origin = request.headers.get('origin');
    if (!isSameOrigin(origin, request.headers.get('host'), isSecure)) {
      return NextResponse.json({ detail: 'Invalid request origin.' }, { status: 403 });
    }
  }

  const publicRead = request.method === 'GET' && (
    route === 'products' ||
    /^products\/\d+$/.test(route) ||
    /^stores\/\d+\/public$/.test(route) ||
    /^stores\/\d+\/public\/images\/(avatar|banner)$/.test(route) ||
    /^users\/\d+\/public\/images\/avatar$/.test(route)
  );
  const access = request.cookies.get('proace_access')?.value;
  const refresh = request.cookies.get('proace_refresh')?.value;
  const headers: Record<string, string> = {};

  if (request.headers.get('content-type')) {
    headers['Content-Type'] = request.headers.get('content-type')!;
  }
  if (paymentWebhook && request.headers.has('stripe-signature')) {
    headers['Stripe-Signature'] = request.headers.get('stripe-signature')!;
  }
  if (access) {
    headers.Authorization = `Bearer ${access}`;
  }

  let body: ArrayBuffer | string | undefined = ['GET', 'HEAD'].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  if (route === 'auth/logout') {
    body = JSON.stringify({ refresh });
    headers['Content-Type'] = 'application/json';
  }
  if (route === 'auth/refresh') {
    return NextResponse.json({ detail: 'Not found.' }, { status: 404 });
  }

  const candidateApis = getCandidateApis(route);
  let upstream: Response | undefined;
  let activeApi = candidateApis[0];
  let lastError: unknown;

  try {
    for (const baseApi of candidateApis) {
      const url = `${baseApi}/${route}/${request.nextUrl.search}`;
      const payload = typeof body === 'string' ? body : body ? body.slice(0) : undefined;
      const isLongRunningStream =
        route === 'notifications/stream' ||
        route.includes('downloads') ||
        route.includes('digital-asset');

      const timeoutSignal = AbortSignal.any([
        request.signal,
        AbortSignal.timeout(isLongRunningStream ? 35000 : 10000),
      ]);

      try {
        upstream = await fetch(url, {
          method: request.method,
          body: payload,
          headers,
          cache: 'no-store',
          redirect: 'manual',
          signal: timeoutSignal,
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
    let newRefresh: string | undefined;
    let invalidRefresh = false;

    if (upstream.status === 401 && refresh && !route.startsWith('auth/')) {
      const authApi: string = getCandidateApis('auth/refresh')[0];
      let renewed: RefreshResult;
      try {
        renewed = await refreshOnce(`${authApi}:${refresh}`, async () => {
          const result = await fetch(`${authApi}/auth/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh }),
            cache: 'no-store',
            signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]),
          });
          const tokens: { access?: string; refresh?: string } = result.ok
            ? await result.json()
            : {};
          return { ...tokens, status: result.status };
        });
      } catch (error: unknown) {
        if (!publicRead || request.signal.aborted) {
          throw error;
        }
        // Temporary refresh failures must not block public anonymous reads or
        // invalidate a refresh cookie that can still work after recovery.
        renewed = { status: 503 };
      }

      invalidRefresh = renewed.status === 400 || renewed.status === 401;
      if (renewed.status >= 500 && !publicRead) {
        return NextResponse.json(
          { detail: 'Authentication is temporarily unavailable. Please retry.' },
          { status: 503 }
        );
      }

      if (renewed.access) {
        newAccess = renewed.access;
        newRefresh = renewed.refresh;
        headers.Authorization = `Bearer ${newAccess}`;
        const url = `${activeApi}/${route}/${request.nextUrl.search}`;
        const payload = typeof body === 'string' ? body : body ? body.slice(0) : undefined;
        const retryTimeoutSignal =
          route === 'notifications/stream' ||
          route.includes('downloads') ||
          route.includes('digital-asset')
            ? AbortSignal.any([request.signal, AbortSignal.timeout(300000)])
            : AbortSignal.any([request.signal, AbortSignal.timeout(10000)]);

        upstream = await fetch(url, {
          method: request.method,
          body: payload,
          headers,
          cache: 'no-store',
          redirect: 'manual',
          signal: retryTimeoutSignal,
        });
      }
    }

    // Public browsing remains available when a saved session is no longer valid.
    // Django still applies its anonymous visibility rules to the retry.
    if (upstream.status === 401 && publicRead && access) {
      delete headers.Authorization;
      upstream = await fetch(`${activeApi}/${route}/${request.nextUrl.search}`, {
        method: 'GET',
        headers,
        cache: 'no-store',
        redirect: 'manual',
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]),
      });
      if (!refresh || invalidRefresh || newAccess) {
        invalidRefresh = true;
        newAccess = undefined;
        newRefresh = undefined;
      }
    }

    if ([301, 302, 303, 307, 308].includes(upstream.status)) {
      const location = upstream.headers.get('location') || '/';
      const response = NextResponse.redirect(new URL(location, request.url), {
        status: upstream.status,
      });
      for (const [name, value] of Object.entries(
        proxyDiagnosticHeaders(upstream.headers, performance.now() - started)
      )) {
        response.headers.set(name, value);
      }
      if (newRefresh) {
        response.cookies.set('proace_refresh', newRefresh, { ...options, maxAge: 604800 });
      }
      if (newAccess) {
        response.cookies.set('proace_access', newAccess, {
          ...options,
          maxAge: accessCookieMaxAge(newAccess),
        });
      }
      return response;
    }

    if (route === 'notifications/stream' && upstream.ok && upstream.body) {
      const response = new NextResponse(upstream.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'X-Accel-Buffering': 'no',
          ...proxyDiagnosticHeaders(upstream.headers, performance.now() - started),
        },
      });
      if (newRefresh) {
        response.cookies.set('proace_refresh', newRefresh, { ...options, maxAge: 604800 });
      }
      if (newAccess) {
        response.cookies.set('proace_access', newAccess, {
          ...options,
          maxAge: accessCookieMaxAge(newAccess),
        });
      }
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
          ...proxyDiagnosticHeaders(upstream.headers, performance.now() - started),
        },
      });
      if (newRefresh) {
        response.cookies.set('proace_refresh', newRefresh, { ...options, maxAge: 604800 });
      }
      if (newAccess) {
        response.cookies.set('proace_access', newAccess, {
          ...options,
          maxAge: accessCookieMaxAge(newAccess),
        });
      }
      if (invalidRefresh) {
        clearAuthCookies(response);
      }
      if (
        route === 'auth/logout' ||
        (route === 'me' && request.method === 'DELETE' && upstream.ok)
      ) {
        clearAuthCookies(response);
      }
      return response;
    }

    const data =
      upstream.status === 204
        ? null
        : await upstream
            .json()
            .catch(() => ({ detail: 'The server could not process this request.' }));

    const loginTokens =
      ['auth/login', 'password/change', 'auth/password', 'auth/google', 'auth/apple', 'auth/social'].includes(route) && upstream.ok
        ? { access: data.access, refresh: data.refresh }
        : null;

    if (loginTokens) {
      delete data.access;
      delete data.refresh;
    }

    const response = NextResponse.json(data, {
      status: upstream.status === 204 ? 200 : upstream.status,
      headers: {
        'Cache-Control': 'no-store',
        ...proxyDiagnosticHeaders(upstream.headers, performance.now() - started),
      },
    });

    if (newRefresh) {
      response.cookies.set('proace_refresh', newRefresh, { ...options, maxAge: 604800 });
    }
    if (newAccess) {
      response.cookies.set('proace_access', newAccess, {
        ...options,
        maxAge: accessCookieMaxAge(newAccess),
      });
    }
    if (loginTokens) {
      response.cookies.set('proace_access', loginTokens.access, {
        ...options,
        maxAge: accessCookieMaxAge(loginTokens.access),
      });
      response.cookies.set('proace_refresh', loginTokens.refresh, {
        ...options,
        maxAge: 604800,
      });
    }

    if (
      route === 'auth/logout'
      || (route === 'me' && request.method === 'DELETE' && upstream.ok)
      || (invalidRefresh && !route.startsWith('auth/'))
    ) {
      clearAuthCookies(response);
    }

    return response;
  } catch (error) {
    console.error(`[API Proxy Error] Failed to proxy ${request.method} /api/${route}:`, error);
    if (route === 'auth/logout') {
      const response = NextResponse.json(null);
      clearAuthCookies(response);
      return response;
    }
    const detail = 'The server is temporarily unavailable. Please try again shortly.';
    return NextResponse.json({ detail }, { status: 503 });
  }
}

export { handler as GET, handler as POST, handler as PATCH, handler as PUT, handler as DELETE };
