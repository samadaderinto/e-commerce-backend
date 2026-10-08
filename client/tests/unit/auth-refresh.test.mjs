import assert from 'node:assert/strict';
import { test } from 'node:test';
import { refreshOnce } from '../../src/lib/auth-refresh.ts';

test('parallel requests share a single refresh and rotated token', async () => {
  let calls = 0;
  const renew = async () => {
    calls++;
    await new Promise((resolve) => setTimeout(resolve, 10));
    return { status: 200, access: 'access', refresh: 'rotated' };
  };

  const results = await Promise.all(
    Array.from({ length: 8 }, () => refreshOnce('test-session', renew))
  );

  assert.equal(calls, 1);
  assert.ok(results.every((value) => value.refresh === 'rotated'));

  await refreshOnce('test-session', renew);
  assert.equal(calls, 1);
});

test('temporary authentication failures can retry without poisoned cache', async () => {
  await refreshOnce('temporary-session', async () => ({ status: 503 }));
  const result = await refreshOnce('temporary-session', async () => ({
    status: 200,
    access: 'recovered',
  }));

  assert.equal(result.access, 'recovered');
});

test('access cookie lifetime follows the upstream token expiration', async () => {
  const { accessCookieMaxAge } = await import('../../src/lib/auth-refresh.ts');
  const exp = Math.floor(Date.now() / 1000) + 3600;
  const token = `header.${Buffer.from(JSON.stringify({ exp })).toString('base64url')}.signature`;

  assert.ok(accessCookieMaxAge(token) >= 3598);
  assert.equal(accessCookieMaxAge('invalid'), 900);
});
