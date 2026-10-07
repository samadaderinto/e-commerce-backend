import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

/**
 * Direct Prometheus Metrics Exporter for the Next.js Frontend.
 * Allows Prometheus to scrape Node.js runtime and frontend telemetry directly.
 */
export async function GET() {
  const uptime = Math.floor(process.uptime());
  const mem = process.memoryUsage();
  const cpu = process.cpuUsage();
  const nodeVersion = process.version;

  const lines = [
    '# HELP frontend_up Process status (1 = healthy, 0 = down)',
    '# TYPE frontend_up gauge',
    'frontend_up 1',
    '',
    '# HELP frontend_uptime_seconds Uptime of the Next.js process in seconds',
    '# TYPE frontend_uptime_seconds counter',
    `frontend_uptime_seconds ${uptime}`,
    '',
    '# HELP frontend_memory_rss_bytes Resident Set Size memory in bytes',
    '# TYPE frontend_memory_rss_bytes gauge',
    `frontend_memory_rss_bytes ${mem.rss}`,
    '',
    '# HELP frontend_memory_heap_used_bytes Heap memory currently used in bytes',
    '# TYPE frontend_memory_heap_used_bytes gauge',
    `frontend_memory_heap_used_bytes ${mem.heapUsed}`,
    '',
    '# HELP frontend_memory_heap_total_bytes Total allocated heap memory in bytes',
    '# TYPE frontend_memory_heap_total_bytes gauge',
    `frontend_memory_heap_total_bytes ${mem.heapTotal}`,
    '',
    '# HELP frontend_memory_external_bytes Memory used by C++ objects bound to JavaScript',
    '# TYPE frontend_memory_external_bytes gauge',
    `frontend_memory_external_bytes ${mem.external}`,
    '',
    '# HELP frontend_cpu_user_seconds_total Total user CPU time spent in seconds',
    '# TYPE frontend_cpu_user_seconds_total counter',
    `frontend_cpu_user_seconds_total ${(cpu.user / 1e6).toFixed(4)}`,
    '',
    '# HELP frontend_cpu_system_seconds_total Total system CPU time spent in seconds',
    '# TYPE frontend_cpu_system_seconds_total counter',
    `frontend_cpu_system_seconds_total ${(cpu.system / 1e6).toFixed(4)}`,
    '',
    '# HELP frontend_node_version Node.js environment information',
    '# TYPE frontend_node_version gauge',
    `frontend_node_version{version="${nodeVersion}"} 1`,
    '',
  ];

  return new NextResponse(lines.join('\n'), {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; version=0.0.4; charset=utf-8',
      'Cache-Control': 'no-store, no-cache, must-revalidate',
    },
  });
}
