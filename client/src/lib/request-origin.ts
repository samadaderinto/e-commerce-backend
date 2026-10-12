/** Validate a browser mutation origin without throwing on malformed headers. */
export function isSameOrigin(
  origin: string | null,
  host: string | null,
  secure: boolean,
): boolean {
  if (!origin || !host) return false;

  try {
    const parsed = new URL(origin);
    return parsed.origin === `${secure ? 'https' : 'http'}://${host}`
      && !parsed.username
      && !parsed.password
      && parsed.pathname === '/'
      && !parsed.search
      && !parsed.hash;
  } catch {
    return false;
  }
}
