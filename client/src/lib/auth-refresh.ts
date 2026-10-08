export type RefreshResult = { access?: string; refresh?: string; status: number };
const renewals = new Map<string, { expires: number; result: Promise<RefreshResult> }>();

/** Share overlapping refreshes, including requests arriving just after rotation. */
export function refreshOnce(key: string, renew: () => Promise<RefreshResult>): Promise<RefreshResult> {
  const now = Date.now();
  for (const [token, entry] of renewals) if (entry.expires <= now) renewals.delete(token);
  const existing = renewals.get(key);
  if (existing) return existing.result;
  const result = renew().then(value => {
    if (value.status >= 500) renewals.delete(key);
    return value;
  }).catch((error: unknown) => { renewals.delete(key); throw error; });
  renewals.set(key, { expires: now + 15000, result });
  setTimeout(() => { if (renewals.get(key)?.result === result) renewals.delete(key); }, 15000).unref?.();
  return result;
}


export function accessCookieMaxAge(token: string): number {
  try {
    const payload: { exp?: number } = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString());
    if (typeof payload.exp === 'number' && Number.isFinite(payload.exp)) return Math.max(0, Math.floor(payload.exp - Date.now() / 1000));
  } catch { /* Test or non-JWT token: use the conservative fallback. */ }
  return 900;
}
