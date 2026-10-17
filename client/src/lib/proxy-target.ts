/** Only the exact SSE route may use the separately configured internal process. */
export function proxyTarget(route: string, apiUrl?: string, streamUrl?: string): string {
  const api: string = apiUrl || 'http://127.0.0.1:8000/api/v1';
  const target: string = route === 'notifications/stream' ? streamUrl || api : api;
  return target.trim().replace(/\/$/, '');
}
