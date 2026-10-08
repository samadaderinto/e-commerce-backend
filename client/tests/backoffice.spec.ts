import { expect, test } from '@playwright/test';

const profile = {id: 7, first_name: 'Taylor', last_name: 'Staff', email: 'staff@test.com', is_staff: true, is_superuser: false, is_business_admin: false, must_change_password: false};
async function mockApi(page: import('@playwright/test').Page, user = profile) {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let json: unknown = {};
    if (path === '/api/me') json = user;
    else if (path === '/api/stores' || path === '/api/admin/staff') json = {count: 0, results: [], next: null};
    else if (path.includes('notifications')) json = {unread: 0, total: 0};
    await route.fulfill({json});
  });
}

test('staff workspace hides shopping, staff administration, and monitoring controls', async ({page}) => {
  await mockApi(page);
  await page.goto('/merchant');
  await expect(page.getByRole('heading', {name: 'No official stores available'})).toBeVisible();
  await expect(page.getByRole('link', {name: 'Seller verification', exact: true})).toHaveCount(0);
  await expect(page.getByRole('link', {name: 'Staff', exact: true})).toHaveCount(0);
  await expect(page.getByRole('link', {name: 'Saved items', exact: true})).toHaveCount(0);
  await expect(page.getByRole('link', {name: 'Live Metrics (Grafana)'})).toHaveCount(0);
  await page.getByRole('button', {name: 'Account and store menu for Taylor'}).click();
  await expect(page.getByRole('link', {name: 'My Orders'})).toHaveCount(0);
  await expect(page.getByRole('link', {name: 'Create your first store'})).toHaveCount(0);
});

test('temporary staff login opens mandatory password form', async ({page}) => {
  await mockApi(page, {...profile, must_change_password: true});
  await page.goto('/merchant');
  await expect(page).toHaveURL(/\/change-password$/);
  await expect(page.getByRole('heading', {name: 'Make this account yours'})).toBeVisible();
  await expect(page.getByRole('navigation', {name: 'Back-office navigation'})).toHaveCount(0);
});

test('business admin staff invitation displays a fixed mask and submits no password', async ({page}) => {
  await mockApi(page, {...profile, is_business_admin: true});
  let submitted: Record<string, unknown> | undefined;
  await page.route('**/api/admin/staff', async route => {
    if (route.request().method() === 'POST') {
      submitted = route.request().postDataJSON();
      await route.fulfill({status: 201, json: {...profile, id: 8, is_active: false}});
    } else await route.fulfill({json: {count: 0, results: []}});
  });
  await page.goto('/admin/staff');
  await page.getByRole('button', {name: 'Add staff', exact: true}).first().click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel('Password generated privately by the server')).toHaveValue('••••••••');
  await expect(dialog.locator('input[name="password"]')).toHaveCount(0);
  await dialog.getByLabel('First name').fill('New');
  await dialog.getByLabel('Last name').fill('Staff');
  await dialog.getByLabel('Email address').fill('new@test.com');
  await dialog.getByLabel('Phone number').fill('+2348012345678');
  await dialog.getByLabel('Gender').selectOption('female');
  await dialog.getByRole('button', {name: 'Create staff account'}).click();
  await expect(dialog).not.toBeVisible();
  expect(submitted?.email).toBe('new@test.com');
  expect(submitted).not.toHaveProperty('password');
});

test('profile store selector fetches more stores when scrolled', async ({page}) => {
  await mockApi(page);
  const offsets: number[] = [];
  await page.route(/\/api\/stores(?:\?|$)/, async route => {
    const url = new URL(route.request().url());
    const offset = Number(url.searchParams.get('offset') || 0);
    if (url.searchParams.get('limit') === '6') offsets.push(offset);
    const results = Array.from({length: offset ? 1 : 6}, (_, index) => ({id: offset + index + 1, name: `Assigned store ${offset + index + 1}`, status: 'blocked', is_official: true}));
    await route.fulfill({json: {count: 7, next: offset ? null : 'next-page', results}});
  });
  await page.goto('/merchant');
  await page.getByRole('button', {name: 'Account and store menu for Taylor'}).click();
  const list = page.locator('.account-dropdown-stores-list');
  await expect(list.getByRole('button', {name: /Assigned store 6/})).toHaveCount(1);
  await list.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(list.getByRole('button', {name: /Assigned store 7/})).toHaveCount(1);
  expect(offsets).toContain(6);
  await expect(page.getByRole('button', {name: 'Next stores page'})).toHaveCount(0);
});

test('staff dashboard exposes audited coupon, refund, and emergency order operations', async ({page}) => {
  await mockApi(page);
  const writes: {path: string; method: string; body?: unknown}[] = [];
  const dashboard = {
    period: {from: '2026-09-01', to: '2026-10-01', days: 30},
    users: {total: 10, active: 9, staff: 2, new: 1},
    stores: {total: 4, active: 3, blocked: 1, new: 1, new_last_30_days: 1},
    financials: {escrow_total: '50.00', commission_earned: '6.00'},
    pending_actions: {withdrawals: 0, refunds: 1},
    products: {total: 20, published: 18, hidden: 2, out_of_stock: 1, sponsored: 0},
    orders: {total: 6, ordered: 5, gross_total: '150.00', by_status: [{status: 'confirmed', count: 3}, {status: 'shipped', count: 2}]},
    coupons: {total: 1, active: 1}, refunds: {total: 1, accepted: 0, declined: 0, pending: 1}, marketers: {total: 2},
    recent_orders: [{id: 44, orderId: 'ORDER44', user: 9, buyer_email: 'buyer@test.com', total: '25.00', status: 'confirmed', created: '2026-10-01T00:00:00Z'}],
    top_stores: [{id: 1, name: 'Store one', username: 'store-one', status: 'active', products: 4, orders: 3}],
  };
  await page.route('**/api/admin/staff/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, '');
    if (route.request().method() !== 'GET') {
      writes.push({path, method: route.request().method(), body: route.request().postDataJSON?.()});
      return route.fulfill({json: {detail: 'Updated'}});
    }
    if (path.endsWith('/dashboard')) return route.fulfill({json: dashboard});
    if (path.endsWith('/coupons')) return route.fulfill({json: {count: 1, results: [{id: 5, code: 'SAVE10', valid_from: '2026-09-01', valid_to: '2026-12-01', discount: 10, num_available: 20, num_used: 0, active: true}]}});
    if (path.endsWith('/refunds')) return route.fulfill({json: {count: 1, results: [{id: 7, email: 'buyer@test.com', order: 44, reason: 'Parcel never arrived', refund_type: 'store_credit', accepted: false, status: 'pending', created: '2026-10-01'}]}});
    return route.fulfill({json: {count: 0, results: []}});
  });
  page.on('dialog', dialog => dialog.accept(dialog.type() === 'prompt' ? 'Verified by support after merchant phone confirmation.' : undefined));
  await page.goto('/admin');
  await expect(page.getByRole('img', {name: 'Order status chart'})).toBeVisible();
  await expect(page.getByRole('link', {name: /Live Metrics/})).toHaveCount(0);
  await page.getByRole('button', {name: 'Deactivate'}).click();
  await page.getByRole('button', {name: 'Approve', exact: true}).click();
  const refundDialog = page.getByRole('dialog');
  await refundDialog.getByLabel('Reason').fill('Verified by support after merchant phone confirmation.');
  await refundDialog.getByRole('button', {name: 'Approve refund', exact: true}).click();
  await expect(refundDialog).not.toBeVisible();
  await page.getByRole('combobox', {name: 'Override status for order ORDER44'}).selectOption('shipped');
  const statusDialog = page.getByRole('dialog');
  await expect(statusDialog.getByRole('button', {name: 'Update status', exact: true})).toBeDisabled();
  await statusDialog.getByLabel('Reason').fill('Verified by support after merchant phone confirmation.');
  await statusDialog.getByRole('button', {name: 'Update status', exact: true}).click();
  await expect.poll(() => writes.length).toBe(3);
  expect(writes.map(write => write.path)).toEqual(expect.arrayContaining([
    '/api/admin/staff/coupons/5',
    '/api/admin/staff/refunds/7/process',
    '/api/admin/staff/orders/44/status',
  ]));
});

test('Grafana links are shown only to the technical admin', async ({ page }) => {
  const data = {
    period: { from: '', to: '', days: 30 },
    users: { total: 0, active: 0, staff: 0, new: 0 },
    stores: { total: 0, active: 0, blocked: 0, new: 0, new_last_30_days: 0 },
    financials: { escrow_total: '0.00', commission_earned: '0.00' },
    pending_actions: { withdrawals: 0, refunds: 0 },
    products: { total: 0, published: 0, hidden: 0, out_of_stock: 0, sponsored: 0 },
    orders: { total: 0, ordered: 0, gross_total: '0', by_status: [] },
    coupons: { total: 0, active: 0 },
    refunds: { total: 0, accepted: 0, declined: 0, pending: 0 },
    marketers: { total: 0 },
    recent_orders: [],
    top_stores: [],
  };

  for (const [role, visible] of [['business', false], ['technical', true]] as const) {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    const user =
      role === 'technical'
        ? { ...profile, is_staff: true, is_superuser: true }
        : { ...profile, is_staff: true, is_business_admin: true };
    await mockApi(page, user);
    await page.route('**/api/admin/staff/**', (route) =>
      route.fulfill({
        json: route.request().url().includes('dashboard') ? data : { count: 0, results: [] },
      })
    );
    await page.goto('/admin');
    await expect(page.getByRole('link', { name: /Live Metrics/ })).toHaveCount(visible ? 1 : 0);
    await expect(page.getByText('Technical admin only')).toHaveCount(visible ? 1 : 0);
  }
});
