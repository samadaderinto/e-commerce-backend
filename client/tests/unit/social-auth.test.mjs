import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  getAppleCredential,
  loadSocialScript,
  renderGoogleSignInButton,
} from '../../src/lib/social-auth.ts';

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

test('Google button rendering reports missing client configuration clearly', async () => {
  const previous = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  try {
    delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

    await assert.rejects(
      renderGoogleSignInButton(
        { replaceChildren() {}, getBoundingClientRect: () => ({ width: 300 }) },
        'signin_with',
        () => {},
        () => {},
      ),
      error => error instanceof Error && error.message === 'Google sign-in is not configured yet.',
    );
  } finally {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    else process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = previous;
  }
});

test('Google uses the rendered provider button and returns its ID token', async () => {
  const previousDocument = globalThis.document;
  const previousWindow = globalThis.window;
  const previousGoogleId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  let initialized;
  let rendered;
  const target = {
    replaceChildren() {},
    getBoundingClientRect: () => ({ width: 320 }),
  };

  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = 'web-client-id';
  globalThis.window = {
    setTimeout,
    clearTimeout,
    google: {
      accounts: {
        id: {
          initialize: config => { initialized = config; },
          renderButton: (parent, options) => { rendered = { parent, options }; },
        },
      },
    },
  };
  globalThis.document = {
    createElement: () => ({ remove() {} }),
    head: { appendChild(script) { script.onload(); } },
  };

  try {
    let returnedCredential = '';
    await renderGoogleSignInButton(
      target,
      'signup_with',
      credential => { returnedCredential = credential; },
      error => { throw error; },
    );

    assert.equal(initialized.client_id, 'web-client-id');
    assert.equal(rendered.parent, target);
    assert.equal(rendered.options.text, 'signup_with');
    assert.equal(rendered.options.width, 320);
    initialized.callback({ credential: 'signed-google-id-token' });
    assert.equal(returnedCredential, 'signed-google-id-token');
  } finally {
    if (previousGoogleId === undefined) delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    else process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = previousGoogleId;
    globalThis.document = previousDocument;
    globalThis.window = previousWindow;
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
