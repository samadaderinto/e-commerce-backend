/** UTC instants are exchanged with the API; calendar inputs use browser local time. */
export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

export function toLocalDateTimeInput(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '';
  const pad = (part: number): string => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** A calendar date is a label, not a UTC instant: never shift it to another day. */
export function calendarDateLabel(value: string): string {
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) ? date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }) : 'Not recorded';
}
