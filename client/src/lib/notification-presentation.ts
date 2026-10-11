const presented: Map<string, number> = new Map<string, number>();

/** SSE and FCM share one foreground presentation identity per account. */
export function presentNotificationOnce(
  recipientId: number,
  notificationId: number | string,
  title: string,
  notify: (message: string) => void,
): void {
  const key: string = `${recipientId}:${notificationId}`;
  if (presented.has(key)) return;
  presented.set(key, Date.now());
  if (presented.size > 500) {
    const oldest: string | undefined = presented.keys().next().value;
    if (oldest) presented.delete(oldest);
  }
  notify(title);
}
