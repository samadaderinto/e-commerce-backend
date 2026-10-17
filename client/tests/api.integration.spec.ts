import { expect, test } from '@playwright/test';

const password = process.env.E2E_DEMO_PASSWORD || 'ProaceDemo2026!';

test('shop search stays public in a browser with stale session cookies', async ({ page, context, baseURL }) => {
  await context.addCookies([
    { name: 'proace_access', value: 'invalid-access', url: baseURL!, httpOnly: true },
    { name: 'proace_refresh', value: 'invalid-refresh', url: baseURL!, httpOnly: true },
  ]);
  await page.goto('/shop?search=xqzzzznosuchitem', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'No finds just yet' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Something interrupted your visit' })).toHaveCount(0);
  const cookies = await context.cookies();
  expect(cookies.some((cookie) => ['proace_access', 'proace_refresh'].includes(cookie.name))).toBe(false);
});

test('public catalog reads recover from stale login cookies', async ({ request }) => {
  for (const cookie of [
    'proace_access=invalid-access',
    'proace_access=invalid-access; proace_refresh=invalid-refresh',
  ]) {
    const catalog = await request.get('/api/products?search=headphones', {
      headers: { cookie },
    });
    expect(catalog.status()).toBe(200);
    const data: { results: { id: number; store: number }[] } = await catalog.json();
    expect(data.results.length).toBeGreaterThan(0);
    expect(catalog.headers()['set-cookie']).toContain('proace_access=;');
    expect(catalog.headers()['set-cookie']).toContain('proace_refresh=;');

    const product = data.results[0];
    for (const route of [
      `/api/products/${product.id}`,
      `/api/stores/${product.store}/public`,
    ]) {
      const response = await request.get(route, { headers: { cookie } });
      expect(response.status()).toBe(200);
    }

    const privateResponse = await request.get('/api/me', { headers: { cookie } });
    expect(privateResponse.status()).toBe(401);
  }
});

test('the Next.js proxy serves the Django catalog and protects private endpoints', async ({ request }) => {
  const catalog = await request.get('/api/products/?search=headphones');
  expect(catalog.status()).toBe(200);
  expect(catalog.headers()['x-request-id']).toMatch(/^[a-f0-9]{32}$/);
  expect(catalog.headers()['x-catalog-cache']).toBe('BYPASS');
  expect(catalog.headers()['server-timing']).toMatch(
    /^app;dur=\d+\.\d{2}, db;dur=\d+\.\d{2}, proxy;dur=\d+\.\d{2}$/
  );
  const results = await catalog.json();
  expect(results.results.length).toBeGreaterThan(0);
  expect(results.results.every((product: { title: string }) => /headphones/i.test(product.title))).toBe(true);

  const profile = await request.get('/api/me/');
  expect(profile.status()).toBe(401);
  expect((await profile.json()).detail).toBeTruthy();
  // A delayed anonymous response must not clear cookies issued by a later login.
  expect(profile.headers()['set-cookie'] || '').not.toMatch(/proace_(access|refresh)=/);

  const mutationWithoutOrigin = await request.post('/api/cart/', {
    data: { product: results.results[0].id, quantity: 1 },
  });
  expect(mutationWithoutOrigin.status()).toBe(403);

  const mutationFromAnotherOrigin = await request.post('/api/cart/', {
    headers: { origin: 'https://attacker.example' },
    data: { product: results.results[0].id, quantity: 1 },
  });
  expect(mutationFromAnotherOrigin.status()).toBe(403);

  const invalidRoute = await request.get('/api/products/untrusted.json');
  expect(invalidRoute.status()).toBe(400);
});

test('login keeps tokens in HttpOnly cookies and returns the authenticated user', async ({ request, baseURL }) => {
  const response = await request.post('/api/auth/login/', {
    headers: { origin: new URL(baseURL!).origin },
    data: { email: 'shopper@proace.local', password },
  });

  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.user.last_login).toEqual(expect.any(String));
  expect(body.user.last_active_at).toEqual(expect.any(String));
  expect(body.user.updated).toEqual(expect.any(String));
  expect(body.user.email).toBe('shopper@proace.local');
  expect(body).not.toHaveProperty('access');
  expect(body).not.toHaveProperty('refresh');

  const cookies = response.headers()['set-cookie'];
  expect(cookies).toContain('proace_access=');
  expect(cookies).toContain('proace_refresh=');
  expect(cookies).toMatch(/proace_access=[^;]+;[^]*HttpOnly/i);
  expect(cookies).toMatch(/proace_refresh=[^;]+;[^]*HttpOnly/i);

  const profile = await request.get('/api/me/');
  expect(profile.status()).toBe(200);
  expect((await profile.json()).email).toBe('shopper@proace.local');
});

test('logout expires root-path auth cookies', async ({ request, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const logout = await request.post('/api/auth/logout/', {
    headers: {
      origin,
      cookie: 'proace_access=expired-access; proace_refresh=expired-refresh',
    },
    data: {},
  });
  // The proxy can return a JSON success (200) or an empty idempotent logout (204).
  expect([200, 204]).toContain(logout.status());
  expect(logout.headers()['set-cookie']).toMatch(/proace_access=; Path=\/;[^]*Max-Age=0/i);
  expect(logout.headers()['set-cookie']).toMatch(/proace_refresh=; Path=\/;[^]*Max-Age=0/i);
});

test('notification stream refreshes stale access through the main authentication API', async ({ request, baseURL }) => {
  const login = await request.post('/api/auth/login', {
    headers: { origin: new URL(baseURL!).origin },
    data: { email: 'shopper@proace.local', password },
  });
  expect(login.status()).toBe(200);
  const state = await request.storageState();
  const cookie: string = state.cookies
    .filter((entry) => ['proace_access', 'proace_refresh'].includes(entry.name))
    .map((entry) => `${entry.name}=${entry.name === 'proace_access' ? 'invalid-access' : entry.value}`)
    .join('; ');
  const controller = new AbortController();
  try {
    const response = await fetch(new URL('/api/notifications/stream', baseURL), {
      headers: { cookie },
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
    });
    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toContain('text/event-stream');
    expect(response.headers.get('set-cookie')).toContain('proace_access=');
    const reader = response.body!.getReader();
    let text: string = '';
    while (!text.includes('event: ready') && text.length < 4096) {
      const chunk = await reader.read();
      if (chunk.done) break;
      text += new TextDecoder().decode(chunk.value);
    }
    expect(text).toContain('event: ready');
    await reader.cancel();
  } finally {
    controller.abort();
  }
});
