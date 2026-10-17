import assert from 'node:assert/strict';
import test from 'node:test';
import { proxyTarget } from '../../src/lib/proxy-target.ts';

test('only notification SSE targets the dedicated process', () => {
  assert.equal(proxyTarget('notifications/stream', 'http://api/api/v1/', 'http://streams/api/v1/'), 'http://streams/api/v1');
  for (const route of ['auth/refresh', 'notifications', 'notifications/counts', 'products', 'notifications/stream/other']) {
    assert.equal(proxyTarget(route, 'http://api/api/v1', 'http://streams/api/v1'), 'http://api/api/v1');
  }
});

test('single-process development needs no dedicated stream URL', () => {
  assert.equal(proxyTarget('notifications/stream'), 'http://127.0.0.1:8000/api/v1');
  assert.equal(proxyTarget('notifications/stream', 'http://api/api/v1', ''), 'http://api/api/v1');
});
