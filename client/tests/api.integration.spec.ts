import { expect, test } from '@playwright/test';

const password = process.env.E2E_DEMO_PASSWORD || 'ProaceDemo2026!';

test('the Next.js proxy serves the Django catalog and protects private endpoints', async ({ request }) => {
  const catalog = await request.get('/api/products/?search=headphones');
  expect(catalog.status()).toBe(200);
  const results = await catalog.json();
  expect(results.results.length).toBeGreaterThan(0);
  expect(results.results.every((product: { title: string }) => /headphones/i.test(product.title))).toBe(true);

  const profile = await request.get('/api/me/');
  expect(profile.status()).toBe(401);
  expect((await profile.json()).detail).toBeTruthy();

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
