import { expect, test } from '@playwright/test';

test.use({ timezoneId: 'Africa/Lagos' });

test('order dates stay readable in staff tables across themes', async ({ page }, testInfo) => {
  await page.route('**/api/**', async route => {
    const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let json: unknown = {};
    if (path === '/api/me') {
      json = { id: 7, first_name: 'Staff', email: 'staff@test.com', is_staff: true };
    } else if (path === '/api/stores') {
      json = { count: 0, results: [] };
    } else if (path === '/api/admin/staff/orders') {
      json = { count: 1, results: [{
        id: 1, orderId: 'DATE-TEST', buyer_email: 'buyer@test.com',
        total: '18.15', status: 'cancelled', payment_type: 'User Wallet',
        created: '2026-10-10T00:00:00Z', updated: '2026-10-10T00:40:44Z',
      }] };
    } else if (path.includes('notifications')) {
      json = { unread: 0, total: 0, results: [] };
    }
    await route.fulfill({ json });
  });
  await page.goto('/admin/orders');
  const table = page.getByRole('table');
  await expect(table.getByRole('columnheader', { name: 'Created', exact: true })).toBeVisible();
  await expect(table.getByRole('columnheader', { name: 'Updated', exact: true })).toBeVisible();
  const row = table.getByRole('row').filter({ hasText: '#DATE-TEST' });
  const dates = row.getByRole('cell').filter({ has: page.locator('.date-stamp') });
  await expect(dates).toHaveCount(2);
  await expect(dates.locator('.date-stamp-label')).toHaveCount(0);
  expect(await row.getByRole('cell').count()).toBe(await table.getByRole('columnheader').count());
  await expect(dates.locator('.date-stamp-day')).toHaveText(['10 Oct 2026', '10 Oct 2026']);
  await expect(dates.locator('.date-stamp-time')).toHaveText(['01:00', '01:40']);
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
    for (const part of await dates.locator('.date-stamp-day, .date-stamp-time').all()) {
      expect(await part.evaluate(element => getComputedStyle(element).whiteSpace)).toBe('nowrap');
    }
    await dates.first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`dates-${theme}.png`), fullPage: true });
  }
});

const created: string = '2026-10-10T00:00:00Z';
const updated: string = '2026-10-10T00:40:44Z';
const store = {
  id: 1, name: 'Date fixture store', username: 'date-store', is_official: true,
  status: 'active', created, updated, last_active_at: updated,
};
const tableCases: {
  path: string;
  endpoint: string;
  headers: string[];
  record: Record<string, unknown>;
}[] = [
  { path: '/admin/stores', endpoint: '/api/admin/staff/stores', headers: ['Created', 'Updated', 'Last active'], record: store },
  {
    path: '/merchant/products', endpoint: '/api/stores/1/products', headers: ['Created', 'Updated', 'Units sold'],
    record: {
      id: 1, title: 'Date fixture product', category: 'electronics', price: '10.00',
      images: [], available: 5, sales: 7, visibility: true, is_digital: false, created,
      updated: null,
    },
  },
  {
    path: '/admin/coupons', endpoint: '/api/admin/staff/coupons', headers: ['Valid from', 'Valid to'],
    record: { id: 1, code: 'DATES', discount: 5, active: true, num_used: 0, num_available: 10, valid_from: created, valid_to: updated },
  },
  {
    path: '/admin/payouts', endpoint: '/api/admin/staff/payouts', headers: ['Requested', 'Processed'],
    record: { id: 1, store: 1, store_name: store.name, reference: 'DATE-PAYOUT', amount: '10.00', payout_method: 'bank_transfer', account_details: {}, status: 'approved', created, processed_at: updated },
  },
];

for (const tableCase of tableCases) {
  test(`${tableCase.path}: date fields occupy separate aligned table columns`, async ({ page }) => {
    await page.route('**/api/**', async route => {
      const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
      let json: unknown = { count: 0, results: [] };
      if (path === '/api/me') json = {
        id: 7, first_name: 'Admin', email: 'admin@test.com', is_staff: true, is_superuser: true,
      };
      else if (path === '/api/stores') json = { count: 1, results: [store] };
      else if (path === '/api/stores/1') json = store;
      else if (path === tableCase.endpoint) json = { count: 1, results: [tableCase.record] };
      else if (path.includes('notifications')) json = { unread: 0, total: 0, results: [] };
      await route.fulfill({ json });
    });
    await page.goto(tableCase.path);
    const table = page.getByRole('table');
    for (const header of tableCase.headers) {
      await expect(table.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    const row = table.locator('tbody tr').first();
    expect(await row.getByRole('cell').count()).toBe(await table.getByRole('columnheader').count());
    await expect(table.locator('.record-dates, .date-stamp-label')).toHaveCount(0);
    await expect(table.getByRole('columnheader', { name: /Created \/|Valid period|^Date$/ })).toHaveCount(0);
    if (tableCase.path === '/merchant/products') {
      const updatedIndex: number = (await table.getByRole('columnheader').allTextContents()).indexOf('Updated');
      await expect(row.getByRole('cell').nth(updatedIndex)).toHaveText('Not recorded');
      const salesIndex: number = (await table.getByRole('columnheader').allTextContents()).indexOf('Units sold');
      await expect(row.getByRole('cell').nth(salesIndex)).toHaveText('7');
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  });
}

const profileRoles: { name: string; is_staff: boolean; is_superuser: boolean }[] = [
  { name: 'Customer', is_staff: false, is_superuser: false },
  { name: 'Staff', is_staff: true, is_superuser: false },
  { name: 'Admin', is_staff: true, is_superuser: true },
];

for (const role of profileRoles) {
  test(`${role.name}: profile activity keeps each label beside its timestamp`, async ({ page }, testInfo) => {
    await page.route('**/api/**', async route => {
      const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
      let json: unknown = { count: 0, results: [] };
      if (path === '/api/me') {
        json = {
          id: 7,
          first_name: role.name,
          last_name: 'Profile',
          email: 'profile@test.com',
          is_staff: role.is_staff,
          is_superuser: role.is_superuser,
          is_active: true,
          updated,
          last_login: created,
          last_active_at: updated,
        };
      } else if (path === '/api/cart') {
        json = { items: [], subtotal: '0', shipping: '0', total: '0' };
      } else if (path === '/api/wishlist') {
        json = [];
      } else if (path.includes('notifications')) {
        json = { unread: 0, total: 0, results: [] };
      }
      await route.fulfill({ json });
    });
    await page.goto('/account/profile');
    const cards = page.locator('.activity-details .activity-detail');
    await expect(cards).toHaveCount(3);
    await expect(cards.locator('dt')).toHaveText(['Last active', 'Last login', 'Profile updated']);
    for (const theme of ['light', 'dark']) {
      await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
      for (const card of await cards.all()) {
        const label = await card.locator('dt').boundingBox();
        const value = await card.locator('dd').boundingBox();
        expect(label).not.toBeNull();
        expect(value).not.toBeNull();
        expect(Math.abs(value!.x - label!.x)).toBeLessThan(2);
        expect(value!.y - label!.y).toBeLessThan(40);
        expect(await card.locator('.date-stamp-value').evaluate(element => getComputedStyle(element).flexDirection)).toBe('row');
        const colors: { background: string; label: string; date: string; time: string } = await card.evaluate(element => ({
          background: getComputedStyle(element).backgroundColor,
          label: getComputedStyle(element.querySelector('dt')!).color,
          date: getComputedStyle(element.querySelector('.date-stamp-day')!).color,
          time: getComputedStyle(element.querySelector('.date-stamp-time')!).color,
        }));
        for (const foreground of [colors.label, colors.date, colors.time]) {
          expect(contrastRatio(foreground, colors.background)).toBeGreaterThanOrEqual(4.5);
        }
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
      await page.screenshot({ path: testInfo.outputPath(`profile-${theme}.png`), fullPage: true });
    }
  });
}


function contrastRatio(foreground: string, background: string): number {
  function luminance(color: string): number {
    const channels: number[] = (color.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
    const linear: number[] = channels.map(channel => {
      const value: number = channel / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    });
    return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
  }
  const first: number = luminance(foreground);
  const second: number = luminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}
