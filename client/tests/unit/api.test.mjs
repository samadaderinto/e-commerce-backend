import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ApiError, api, categories, money } from '../../src/lib/api.ts';

test('formats NGN amounts without fractional digits', () => {
  assert.match(money(1500), /1,500/);
  assert.match(money('25000.75'), /25,001/);
});

test('exposes the supported storefront categories', () => {
  assert.deepEqual(categories.map(({ key }) => key), [
    'electronics',
    'outwear',
    'phones',
    'computing',
    'sports',
    'books',
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

test('uses a safe message when the API returns a non-JSON error', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('unavailable', { status: 503 }));

  await assert.rejects(
    api('products'),
    error => error instanceof ApiError
      && error.status === 503
      && error.message === 'Something went wrong. Please try again.',
  );
});
