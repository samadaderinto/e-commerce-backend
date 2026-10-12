import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isSameOrigin } from '../../src/lib/request-origin.ts';

test('mutation origins reject malformed, opaque, foreign, and insecure headers', () => {
  for (const origin of [null, 'null', 'invalid', 'https://other.test', 'http://shop.test', 'https://shop.test/path', 'https://user:secret@shop.test']) {
    assert.equal(isSameOrigin(origin, 'shop.test', true), false);
  }
  assert.equal(isSameOrigin('https://shop.test', 'shop.test', true), true);
  assert.equal(isSameOrigin('http://localhost:3000', 'localhost:3000', false), true);
});
