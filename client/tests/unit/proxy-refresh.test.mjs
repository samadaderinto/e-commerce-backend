import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const source = fs.readFileSync(new URL('../../src/app/api/[...path]/route.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

async function exercise({ route = 'products', method = 'GET', failure = 'network', aborted = false, trusted = false, forwardedProto = 'http', asset = false } = {}) {
  const calls = [];
  const cookies = [];
  const timers = new Set();
  class MockResponse extends Response {
    cookies = { set: (...args) => cookies.push(args) };
    static json(body, options) {
      return new MockResponse(JSON.stringify(body), {
        ...options, headers: { 'Content-Type': 'application/json' },
      });
    }
  }
  const module = { exports: {} };
  const context = vm.createContext({
    module, exports: module.exports, Response, Headers, URL, AbortSignal, AbortController,
    setTimeout(callback) { timers.add(callback); return callback; },
    clearTimeout(timer) { timers.delete(timer); },
    performance, process: { env: { ...process.env, TRUSTED_EDGE_PROXY: trusted ? 'true' : 'false' } }, console: { error() {} },
    require(name) {
      if (name === 'next/server') return { NextResponse: MockResponse };
      if (name.endsWith('/auth-refresh')) {
        return { refreshOnce: (_key, renew) => renew(), accessCookieMaxAge: () => 900 };
      }
      if (name.endsWith('/request-origin')) return { isSameOrigin: () => true };
      if (name.endsWith('/proxy-diagnostics')) return { proxyDiagnosticHeaders: () => ({}) };
      if (name.endsWith('/proxy-target')) return { proxyTarget: () => 'http://backend.test/api/v1' };
      throw new Error(`Unexpected import: ${name}`);
    },
    async fetch(url, options) {
      calls.push({ path: new URL(url).pathname, authorization: options.headers.Authorization, protocol: options.headers['X-Forwarded-Proto'], signal: options.signal });
      if (asset) return new Response('purchased bytes', { headers: { 'Content-Type': 'application/octet-stream' } });
      if (url.includes('/auth/refresh/')) {
        if (failure === 'network') throw new TypeError('Controlled fetch failure');
        if (failure === 'timeout') throw new DOMException('Timed out', 'TimeoutError');
        if (failure === 'malformed') return new Response('invalid JSON');
        return Response.json({ detail: 'Unavailable' }, { status: 503 });
      }
      return options.headers.Authorization
        ? Response.json({ detail: 'Expired' }, { status: 401 })
        : Response.json({ count: 1, results: [{ id: 1 }] });
    },
  });
  vm.runInContext(compiled, context);
  const controller = new AbortController();
  if (aborted) controller.abort();
  const request = {
    method, url: `http://frontend.test/api/${route}`,
    nextUrl: new URL(`http://frontend.test/api/${route}`),
    headers: new Headers({ host: 'frontend.test', 'x-forwarded-proto': forwardedProto }),
    cookies: { get: name => ({ value: name === 'proace_access' ? 'expired' : 'refresh-fixture' }) },
    signal: controller.signal,
    arrayBuffer: async () => new ArrayBuffer(0),
  };
  const response = await module.exports[method](request, {
    params: Promise.resolve({ path: route.split('/') }),
  });
  return { response, calls, cookies, timers, controller };
}

for (const failure of ['network', 'timeout', 'malformed', 'http']) {
  test(`public browsing survives ${failure} refresh failure without clearing cookies`, async () => {
    const { response, calls, cookies } = await exercise({ failure });
    assert.equal(response.status, 200);
    assert.equal(calls.length, 3);
    assert.equal(calls[2].authorization, undefined);
    assert.deepEqual(cookies, []);
  });
}

test('refresh outages do not fall back anonymously for private reads or writes', async () => {
  for (const options of [{ route: 'me' }, { route: 'cart', method: 'POST' }]) {
    const { response, calls } = await exercise(options);
    assert.equal(response.status, 503);
    assert.equal(calls.length, 2);
  }
});

test('cancelled public requests do not trigger anonymous recovery', async () => {
  const { response, calls } = await exercise({ aborted: true });
  assert.equal(response.status, 503);
  assert.equal(calls.length, 2);
});


test('trusted HTTPS metadata reaches both initial API call and token refresh', async () => {
  const { calls } = await exercise({ trusted: true, forwardedProto: 'https' });
  assert.equal(calls[0].protocol, 'https');
  assert.equal(calls[1].protocol, 'https');
});

test('a public standalone listener ignores client supplied HTTPS metadata', async () => {
  const { calls } = await exercise({ trusted: false, forwardedProto: 'https' });
  assert.equal(calls[0].protocol, 'http');
  assert.equal(calls[1].protocol, 'http');
});

test('download header deadline is cleared before body streaming and client cancellation remains active', async () => {
  const { response, calls, timers, controller } = await exercise({ route: 'orders/1/downloads/2', asset: true });
  assert.equal(response.status, 200);
  assert.equal(timers.size, 0);
  assert.equal(calls[0].signal.aborted, false);
  assert.equal(await response.text(), 'purchased bytes');
  controller.abort();
  assert.equal(calls[0].signal.aborted, true);
});
