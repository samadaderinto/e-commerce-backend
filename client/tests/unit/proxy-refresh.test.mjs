import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const source = fs.readFileSync(new URL('../../src/app/api/[...path]/route.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

async function exercise({ route = 'products', method = 'GET', failure = 'network', aborted = false } = {}) {
  const calls = [];
  const cookies = [];
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
    module, exports: module.exports, Response, Headers, URL, AbortSignal,
    performance, process, console: { error() {} },
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
      calls.push({ path: new URL(url).pathname, authorization: options.headers.Authorization });
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
    headers: new Headers({ host: 'frontend.test' }),
    cookies: { get: name => ({ value: name === 'proace_access' ? 'expired' : 'refresh-fixture' }) },
    signal: controller.signal,
    arrayBuffer: async () => new ArrayBuffer(0),
  };
  const response = await module.exports[method](request, {
    params: Promise.resolve({ path: route.split('/') }),
  });
  return { response, calls, cookies };
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
