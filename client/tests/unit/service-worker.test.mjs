import assert from 'node:assert/strict';
import test from 'node:test';

import { waitForActiveServiceWorker } from '../../src/lib/service-worker.ts';

class MockServiceWorker extends EventTarget {
  state = 'installing';

  activate() {
    this.state = 'activated';
    this.dispatchEvent(new Event('statechange'));
  }

  fail() {
    this.state = 'redundant';
    this.dispatchEvent(new Event('statechange'));
  }
}

test('push registration waits for the installing worker to activate', async () => {
  const worker = new MockServiceWorker();
  const registration = {
    active: null,
    installing: worker,
    waiting: null,
  };

  const activeRegistration = waitForActiveServiceWorker(registration, 100);
  worker.activate();

  assert.equal(await activeRegistration, registration);
});

test('push registration accepts an already active worker', async () => {
  const registration = {
    active: { state: 'activated' },
    installing: null,
    waiting: null,
  };

  assert.equal(await waitForActiveServiceWorker(registration), registration);
});

test('push registration reports a worker that becomes redundant', async () => {
  const worker = new MockServiceWorker();
  const registration = {
    active: null,
    installing: worker,
    waiting: null,
  };
  const activeRegistration = waitForActiveServiceWorker(registration, 100);
  worker.fail();

  await assert.rejects(activeRegistration, /could not be activated/);
});
