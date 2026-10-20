import { expect, test, type Route } from '@playwright/test';
import type { NotificationFiltersMeta, User } from '../src/lib/types';

for (const role of ['technical_admin', 'business_admin', 'staff', 'customer'] as const) {
  test(`${role} can filter received notifications by independent store`, async ({ page }) => {
    const user: User = {
      id: 9908,
      email: 'notification-audit@example.test',
      first_name: 'Notification',
      last_name: 'Reviewer',
      phone1: '',
      is_staff: role !== 'customer',
      is_superuser: role === 'technical_admin',
      is_business_admin: role === 'business_admin',
      must_change_password: false,
      role,
    };
    const metadata: NotificationFiltersMeta = {
      categories: [{ id: 'all', label: 'All Categories', count: 0 }],
      stores: [
        { id: 21, name: 'Independent received store', username: 'independent', is_official: false },
        { id: 22, name: 'Official received store', username: 'official', is_official: true },
      ],
      counts: { unread: 0, read: 0, archived: 0, total: 0 },
    };
    await page.route('**/api/**', async (route: Route): Promise<void> => {
      const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
      if (path === '/api/notifications/stream') {
        await route.fulfill({ contentType: 'text/event-stream', body: ': mocked stream\n\n' });
        return;
      }
      let json: unknown = { count: 0, results: [] };
      if (path === '/api/me') json = user;
      if (path === '/api/notifications/filters') json = metadata;
      if (path === '/api/notifications/counts') json = metadata.counts;
      if (path === '/api/stores') json = [];
      if (path === '/api/cart') json = { items: [], subtotal: '0', total: '0', shipping: '0' };
      if (path === '/api/wishlist') json = [];
      await route.fulfill({ json });
    });

    await page.goto('/notifications', { waitUntil: 'domcontentloaded' });
    const filter = page.getByRole('combobox', { name: 'Filter by store' });
    await expect(filter.locator('option')).toHaveText([
      'All stores (2)', 'Independent received store', 'Official received store',
    ]);
    const filteredRequest = page.waitForRequest(request => {
      const url: URL = new URL(request.url());
      return url.pathname === '/api/notifications' && url.searchParams.get('store') === '21';
    });
    await filter.selectOption('21');
    await filteredRequest;
    await expect(filter).toHaveValue('21');
    await page.getByRole('button', { name: 'Reset filters', exact: true }).click();
    await expect(filter).toHaveValue('all');
  });
}
