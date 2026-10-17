import assert from 'node:assert/strict';
import test from 'node:test';
import { proxyDiagnosticHeaders } from '../../src/lib/proxy-diagnostics.ts';

test('proxy preserves safe correlation/cache diagnostics and adds inclusive timing', () => {
  const result = proxyDiagnosticHeaders(new Headers({
    'x-request-id': 'a'.repeat(32),
    'x-catalog-cache': 'BYPASS',
    'server-timing': 'app;dur=12.00, db;dur=2.00',
    authorization: 'secret',
    'set-cookie': 'private=value',
  }), 15.25);
  assert.deepEqual(result, {
    'X-Request-ID': 'a'.repeat(32),
    'X-Catalog-Cache': 'BYPASS',
    'Server-Timing': 'app;dur=12.00, db;dur=2.00, proxy;dur=15.25',
  });
});

test('proxy rejects arbitrary backend diagnostic values', () => {
  const result = proxyDiagnosticHeaders(new Headers({
    'x-request-id': 'private-internal-value',
    'x-catalog-cache': 'internal-key',
    'server-timing': 'sql;desc="private query"',
  }), 2);
  assert.deepEqual(result, { 'Server-Timing': 'proxy;dur=2.00' });
});
