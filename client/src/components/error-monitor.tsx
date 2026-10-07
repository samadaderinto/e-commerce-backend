'use client';

import { useEffect } from 'react';
import type { FrontendLogEntry } from '@/lib/loki-logger';

function sendTelemetry(entry: FrontendLogEntry) {
  void fetch('/api/logs', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(entry), keepalive: true }).catch(() => undefined);
}

/**
 * Direct-to-Monitoring Frontend Error Interceptor.
 * Captures uncaught browser errors & promise rejections and forwards them
 * directly to the Grafana Loki endpoint with no backend intermediary.
 */
export function ErrorMonitor() {
  useEffect(() => {
    if (typeof window === 'undefined') return;

    let errorCount = 0;
    const MAX_ERRORS_PER_SESSION = 15;

    const handleWindowError = (event: ErrorEvent) => {
      if (errorCount >= MAX_ERRORS_PER_SESSION) return;
      errorCount++;

      sendTelemetry({
        level: 'error',
        message: event.message || 'Uncaught browser exception',
        stack: event.error?.stack,
        url: event.filename || window.location.href,
        context: {
          lineno: event.lineno,
          colno: event.colno,
          screen: `${window.innerWidth}x${window.innerHeight}`,
        },
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      if (errorCount >= MAX_ERRORS_PER_SESSION) return;
      errorCount++;

      const reason = event.reason;
      const message =
        typeof reason === 'string'
          ? reason
          : reason?.message || 'Unhandled Promise Rejection';
      const stack = reason?.stack;

      sendTelemetry({
        level: 'error',
        message,
        stack,
        url: window.location.href,
        context: {
          type: 'unhandledrejection',
          screen: `${window.innerWidth}x${window.innerHeight}`,
        },
      });
    };

    window.addEventListener('error', handleWindowError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleWindowError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  return null;
}
