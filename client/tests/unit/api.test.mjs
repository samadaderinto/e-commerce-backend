import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ApiError, api, cancelPendingApiRequests, categories, money } from '../../src/lib/api.ts';

test('formats USD amounts with cents when needed', () => {
  assert.match(money(1500), /1,500/);
  assert.match(money('25000.75'), /25,000\.75/);
});

test('exposes the supported storefront categories', () => {
  assert.deepEqual(categories.map(({ key }) => key), [
    'electronics',
    'outwear',
    'phones',
    'computing',
    'sports',
    'books',
    'toys',
    'kids',
    'home',
    'kitchen',
    'beauty',
    'health',
    'pets',
    'games',
    'tablets',
    'fishing',
    'lingerie',
    'beverages',
    'garden',
    'automotive',
    'jewelry',
    'software',
    'courses',
    'templates',
    'design_assets',
    'photo_video',
    'music_audio',
    'business',
    'digital_tools',

  ]);
});

test('sends JSON through the same-origin API proxy', async t => {
  let captured;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    captured = { url, options };
    return Response.json({ ok: true });
  });

  assert.deepEqual(await api('cart', 'POST', { product: 7, quantity: 2 }), { ok: true });
  assert.equal(captured.url, '/api/cart');
  assert.equal(captured.options.method, 'POST');
  assert.equal(captured.options.credentials, 'same-origin');
  assert.equal(captured.options.headers['Content-Type'], 'application/json');
  assert.equal(captured.options.body, JSON.stringify({ product: 7, quantity: 2 }));
});

test('logout can abort pending API requests that might refresh authentication cookies', async t => {
  let requestSignal;
  let markStarted;
  const started = new Promise(resolve => { markStarted = resolve; });
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    requestSignal = options.signal;
    markStarted();
    return new Promise((_resolve, reject) => {
      requestSignal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    });
  });

  const pending = api('me').catch(error => error);
  await started;
  cancelPendingApiRequests();
  const error = await pending;
  assert.equal(requestSignal.aborted, true);
  assert.ok(error instanceof ApiError);
  assert.equal(error.status, 503);
});

test('does not set multipart content type for file uploads', async t => {
  let captured;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    captured = { url, options };
    return Response.json({ uploaded: true });
  });
  const data = new FormData();
  data.set('image', new Blob(['photo']), 'photo.png');

  assert.deepEqual(await api('stores/1/products', 'POST', data), { uploaded: true });
  assert.equal(captured.options.headers, undefined);
  assert.equal(captured.options.body, data);
});

test('turns API validation errors into readable ApiErrors', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json(
    { detail: 'Invalid input.', postal_code: ['This field is required.'] },
    { status: 400 },
  ));

  await assert.rejects(
    api('addresses', 'POST', {}),
    error => error instanceof ApiError
      && error.status === 400
      && error.message === 'Invalid input. postal code: This field is required.',
  );
});

test('unwraps Python ErrorDetail strings and omits technical field prefixes', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json(
    { code: "{'coupon': ErrorDetail(string='This coupon does not apply to anything in your cart.', code='invalid')}" },
    { status: 400 },
  ));

  await assert.rejects(
    api('checkout/validate-coupon', 'POST', {}),
    error => error instanceof ApiError
      && error.status === 400
      && error.message === 'This coupon does not apply to anything in your cart.',
  );
});

test('unwraps DRF error envelope and strips non_field_errors prefix', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json(
    {
      error: {
        code: 'invalid',
        message: 'Request validation failed.',
        details: {
          non_field_errors: ['Unable to log in with provided credentials.'],
        },
      },
    },
    { status: 400 },
  ));

  await assert.rejects(
    api('auth/login', 'POST', {}),
    error => error instanceof ApiError
      && error.status === 400
      && error.message === 'Unable to log in with provided credentials.',
  );
});

test('uses a safe message when the API returns a non-JSON error', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('unavailable', { status: 503 }));

  await assert.rejects(
    api('products'),
    error => error instanceof ApiError
      && error.status === 503
      && error.message === 'Something went wrong. Please try again.',
  );
});

test('returns a readable error when a backend request times out', async t => {
  t.mock.method(globalThis, 'fetch', async () => {
    throw new DOMException('Timed out', 'TimeoutError');
  });
  await assert.rejects(api('auth/login', 'POST', { email: 'shopper@proace.local' }),
    error => error instanceof ApiError && error.status === 503
      && error.message === 'The server took too long to respond. Please try again shortly.');
});

test('forwards notification query filters including search, store, and category', async t => {
  let captured;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    captured = { url, options };
    return Response.json({ count: 1, results: [] });
  });

  const query = 'notifications?limit=15&offset=0&category=store&store=3&search=refund';
  const result = await api(query);
  assert.equal(captured.url, `/api/${query}`);
  assert.equal(captured.options.method, 'GET');
  assert.equal(result.count, 1);
});

