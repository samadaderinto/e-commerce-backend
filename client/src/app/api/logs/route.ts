import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

interface ClientLogPayload {
  level?: 'error' | 'warn' | 'info';
  message: string;
  stack?: string;
  url?: string;
  userAgent?: string;
  timestamp?: string;
  info?: Record<string, unknown>;
}

export async function POST(request: NextRequest) {
  try {
    const raw = await request.json().catch(() => null);
    if (!raw || typeof raw !== 'object') {
      return NextResponse.json({ error: 'Invalid log payload' }, { status: 400 });
    }

    const payload = raw as ClientLogPayload;
    const level = ['error', 'warn', 'info'].includes(payload.level || '') ? payload.level : 'error';
    const message = String(payload.message || 'Unknown client error').slice(0, 1000);
    const stack = payload.stack ? String(payload.stack).slice(0, 3000) : undefined;
    const url = payload.url ? String(payload.url).slice(0, 500) : request.headers.get('referer') || undefined;
    const userAgent = request.headers.get('user-agent') || undefined;

    // Structured JSON log output to stdout - scraped automatically by Alloy into Loki
    const logEntry = {
      timestamp: new Date().toISOString(),
      service_name: 'client',
      source: 'frontend-browser',
      level,
      message,
      stack,
      url,
      userAgent,
      metadata: payload.info,
    };

    const serialized = JSON.stringify(logEntry);
    if (level === 'error') {
      console.error(serialized);
    } else if (level === 'warn') {
      console.warn(serialized);
    } else {
      console.log(serialized);
    }

    return NextResponse.json({ received: true }, { status: 202 });
  } catch (error) {
    console.error('[Frontend Log Ingestion Error]', error);
    return NextResponse.json({ error: 'Failed to ingest log' }, { status: 500 });
  }
}
