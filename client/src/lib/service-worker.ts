export function waitForActiveServiceWorker(
  registration: ServiceWorkerRegistration,
  timeoutMs: number = 10000,
): Promise<ServiceWorkerRegistration> {
  if (registration.active?.state === 'activated') {
    return Promise.resolve(registration);
  }

  const worker = registration.installing ?? registration.waiting ?? registration.active;
  if (!worker) {
    return Promise.reject(new Error('The push service worker could not be started.'));
  }

  return new Promise((resolve, reject) => {
    let timeout: ReturnType<typeof setTimeout> | undefined;

    const cleanup = (): void => {
      worker.removeEventListener('statechange', checkState);
      if (timeout !== undefined) clearTimeout(timeout);
    };

    const checkState = (): void => {
      if (worker.state === 'activated') {
        cleanup();
        resolve(registration);
      } else if (worker.state === 'redundant') {
        cleanup();
        reject(new Error('The push service worker could not be activated. Please try again.'));
      }
    };

    worker.addEventListener('statechange', checkState);
    timeout = setTimeout(() => {
      cleanup();
      reject(new Error('The push service worker is taking longer than expected. Please try again.'));
    }, timeoutMs);
    checkState();
  });
}
