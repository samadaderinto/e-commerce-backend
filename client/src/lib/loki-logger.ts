/**
 * Direct-to-Monitoring Loki Log Shipper.
 * Sends frontend logs and exceptions directly to Grafana Loki's HTTP push API
 * without routing through any backend proxy.
 */

const LOKI_ENDPOINT =
  typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_LOKI_URL || 'http://127.0.0.1:3100').replace(/\/$/, '')
    : 'http://loki:3100';

export interface FrontendLogEntry {
  level?: 'error' | 'warn' | 'info';
  message: string;
  stack?: string;
  url?: string;
  context?: Record<string, unknown>;
}

/**
 * Pushes structured logs directly to Loki via its /loki/api/v1/push endpoint.
 */
export async function sendDirectToLoki(entry: FrontendLogEntry): Promise<boolean> {
  const level = entry.level || 'info';
  const timestampNs = (Date.now() * 1000000).toString();

  const logPayload = {
    message: entry.message,
    stack: entry.stack,
    url: entry.url || (typeof window !== 'undefined' ? window.location.href : undefined),
    userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
    context: entry.context,
    timestamp: new Date().toISOString(),
  };

  const body = JSON.stringify({
    streams: [
      {
        stream: {
          app: 'proace-frontend',
          service_name: 'client',
          source: 'browser',
          level,
        },
        values: [[timestampNs, JSON.stringify(logPayload)]],
      },
    ],
  });

  try {
    const pushUrl = `${LOKI_ENDPOINT}/loki/api/v1/push`;
    const res = await fetch(pushUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
      mode: 'cors',
      credentials: 'omit',
    });
    return res.status === 204 || res.status === 200;
  } catch (err) {
    // Fail silently in production console so telemetry errors don't cascade
    if (process.env.NODE_ENV === 'development') {
      console.debug('[Direct Loki Push Notice] Could not reach Loki at', LOKI_ENDPOINT, err);
    }
    return false;
  }
}
