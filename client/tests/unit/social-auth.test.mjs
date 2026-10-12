import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getAppleCredential, getGoogleCredential, loadSocialScript } from '../../src/lib/social-auth.ts';

test('provider scripts wait for shared loading and recover after a failed load', async () => {
  const previousDocument = globalThis.document;
  const previousWindow = globalThis.window;
  const scripts = [];
  globalThis.window = { setTimeout, clearTimeout };
  globalThis.document = {
    createElement: () => ({ remove() { this.removed = true; } }),
    head: { appendChild(script) { scripts.push(script); } },
  };
  try {
    const first = loadSocialScript('https://provider.test/sdk.js', 'audit-provider');
    const concurrent = loadSocialScript('https://provider.test/sdk.js', 'audit-provider');
    assert.equal(first, concurrent);
    assert.equal(scripts.length, 1);
    scripts[0].onerror();
    await assert.rejects(first, /Unable to load/);
    assert.equal(scripts[0].removed, true);
    const retry = loadSocialScript('https://provider.test/sdk.js', 'audit-provider');
    assert.equal(scripts.length, 2);
    scripts[1].onload();
    await retry;
  } finally {
    globalThis.document = previousDocument;
    globalThis.window = previousWindow;
  }
});

test('google sign-in reports missing client configuration clearly', async () => {
  const previous = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  try {
    delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

    await assert.rejects(
      getGoogleCredential(),
      error => error instanceof Error && error.message === 'Google sign-in is not configured yet.',
    );
  } finally {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    else process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = previous;
  }
});

test('apple sign-in reports missing client configuration clearly', async () => {
  const previous = process.env.NEXT_PUBLIC_APPLE_CLIENT_ID;
  try {
    delete process.env.NEXT_PUBLIC_APPLE_CLIENT_ID;

    await assert.rejects(
      getAppleCredential(),
      error => error instanceof Error && error.message === 'Apple sign-in is not configured yet.',
    );
  } finally {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_APPLE_CLIENT_ID;
    else process.env.NEXT_PUBLIC_APPLE_CLIENT_ID = previous;
  }
});
