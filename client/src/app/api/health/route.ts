import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

function getUpstreamUrl(): string {
  const configured = (process.env.API_URL || 'http://127.0.0.1:8000/api/v1').trim();
  const base = configured.replace(/\/api\/v1\/?$/, '');
  return `${base}/health/live/`;
}

export async function GET() {
  const startedAt = Date.now();
  const uptimeSeconds = Math.floor(process.uptime());

  let upstreamStatus = 'unknown';
  let upstreamLatencyMs = 0;
  let upstreamError: string | undefined;

  const upstreamTarget = getUpstreamUrl();
  try {
    const upstreamStart = Date.now();
    const res = await fetch(upstreamTarget, {
      method: 'GET',
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    upstreamLatencyMs = Date.now() - upstreamStart;
    upstreamStatus = res.ok ? 'healthy' : `unhealthy (${res.status})`;
  } catch (err: unknown) {
    upstreamStatus = 'unreachable';
    upstreamError = err instanceof Error ? err.message : String(err);
  }

  const memoryUsage = process.memoryUsage();

  const payload = {
    status: 'ok',
    service: 'client',
    timestamp: new Date().toISOString(),
    uptime_seconds: uptimeSeconds,
    process: {
      node_version: process.version,
      memory: {
        rss_mb: Math.round(memoryUsage.rss / (1024 * 1024)),
        heap_used_mb: Math.round(memoryUsage.heapUsed / (1024 * 1024)),
      },
    },
    upstream: {
      target: upstreamTarget,
      status: upstreamStatus,
      latency_ms: upstreamLatencyMs,
      error: upstreamError,
    },
    response_time_ms: Date.now() - startedAt,
  };

  return NextResponse.json(payload, {
    status: 200,
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate',
    },
  });
}
