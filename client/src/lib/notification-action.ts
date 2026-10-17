type ActionSource = {
  category?: string;
  data?: Record<string, unknown> | null;
};

export type NotificationAction = { href: string; label: string };

export function notificationAction(item: ActionSource): NotificationAction | null {
  const href = item.data?.url;
  if (typeof href !== 'string' || !href.startsWith('/') || href.startsWith('//') || /[\\\u0000-\u0020]/.test(href)) {
    return null;
  }
  if (href === '/notifications') return null;
  const labels: Record<string, string> = {
    order: 'View order',
    refund: href.startsWith('/admin/refunds') || href.startsWith('/merchant/refunds') ? 'View refund' : 'View order',
    payout: 'View payout',
    wallet: 'View wallet',
    store: 'View store',
    account: 'View account',
    affiliates: 'View referral activity',
  };
  return { href, label: labels[item.category || ''] || 'View details' };
}
