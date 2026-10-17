import { expect, test } from '@playwright/test';

const profile = {id: 7, first_name: 'Taylor', last_name: 'Staff', email: 'staff@test.com', is_staff: true, is_superuser: false, is_business_admin: false, must_change_password: false};
async function mockApi(page: import('@playwright/test').Page, user = profile) {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let json: unknown = {};
    if (path === '/api/me') json = user;
    else if (path === '/api/stores' || path === '/api/admin/staff') json = {count: 0, results: [], next: null};
    else if (path === '/api/admin/staff/orders') json = {count: 0, results: []};
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

test('treasury withdrawal uses saved bank selection and completes without a stale event error', async ({ page }) => {
  const admin = { ...profile, is_business_admin: true };
  let withdrawalPayload: Record<string, unknown> | null = null;
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ json: admin });
    if (path === '/api/admin/staff/commission-wallet/withdraw' && request.method() === 'POST') {
      withdrawalPayload = request.postDataJSON() as Record<string, unknown>;
      return route.fulfill({ status: 201, json: { id: 3, reference: 'PCW-test', status: 'pending' } });
    }
    if (path === '/api/admin/staff/commission-wallet') {
      return route.fulfill({ json: {
        earned: '100.00', marketplace_commission: '75.00', official_stores_revenue: '25.00',
        withdrawn_or_pending: '0.00', available: '100.00', withdrawal_count: 0, withdrawals: [],
      } });
    }
    if (path === '/api/bank-accounts') {
      return route.fulfill({ json: [{
        id: 81, bank_name: 'Kuda Bank', account_holder_name: 'Taylor Staff',
        account_last4: '7890', routing_last4: '2345', is_default: true,
      }] });
    }
    if (path.includes('notifications')) return route.fulfill({ json: { unread: 0, total: 0 } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/admin/commission');
  await expect(page.locator('.treasury-stats-grid > .stat-item')).toHaveCount(5);
  const statCards = await page.locator('.treasury-stats-grid > .stat-item').all();
  const statCardPositions = await Promise.all(statCards.map(card => card.boundingBox()));
  expect(statCardPositions.every(position => position !== null)).toBe(true);
  if ((page.viewportSize()?.width || 0) > 900) {
    expect(new Set(statCardPositions.map(position => Math.round(position!.y))).size).toBe(1);
  }
  await page.getByRole('spinbutton', { name: 'Amount', exact: true }).fill('25.00');
  await page.getByLabel('Payout method').selectOption('bank');
  await expect(page.getByText('Kuda Bank · Default', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Change', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Manage payout accounts' })).toHaveAttribute('href', '/account/payout-accounts');
  await expect(page.locator('.treasury-bank-picker > .text-link')).toHaveCount(0);
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Edit bank account' })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Change', exact: true }).click();
  await page.getByRole('button', { name: /Kuda Bank/ }).click();
  await page.getByRole('button', { name: 'Request withdrawal' }).click();
  await expect(page.getByText('Platform treasury withdrawal request created')).toBeVisible();
  await expect.poll(() => withdrawalPayload).not.toBeNull();
  expect(withdrawalPayload).toMatchObject({ amount: '25.00', payout_method: 'bank', bank_account_id: 81 });
  await expect(page.getByText("Cannot read properties of null", { exact: false })).toHaveCount(0);
});

test('treasury Stripe transfer uses a saved destination ID and never submits a placeholder', async ({ page }) => {
  const admin = { ...profile, is_business_admin: true };
  let withdrawalPayload: Record<string, unknown> | null = null;
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ json: admin });
    if (path === '/api/admin/staff/commission-wallet/withdraw' && request.method() === 'POST') {
      withdrawalPayload = request.postDataJSON() as Record<string, unknown>;
      return route.fulfill({ status: 201, json: { id: 4, reference: 'PCW-stripe', status: 'pending' } });
    }
    if (path === '/api/admin/staff/commission-wallet') {
      return route.fulfill({ json: {
        earned: '100.00', marketplace_commission: '75.00', official_stores_revenue: '25.00',
        withdrawn_or_pending: '0.00', available: '100.00', withdrawal_count: 0, withdrawals: [],
      } });
    }
    if (path === '/api/stripe-payout-destinations') {
      return route.fulfill({ json: [{
        id: 92, label: 'Treasury Stripe', account_id_last4: 'BCDE', is_default: true,
      }] });
    }
    if (path.includes('notifications')) return route.fulfill({ json: { unread: 0, total: 0 } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/admin/commission');
  await page.getByRole('spinbutton', { name: 'Amount', exact: true }).fill('25.00');
  await expect(page.getByText('Treasury Stripe · Default', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Change', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Manage payout accounts' })).toHaveAttribute('href', '/account/payout-accounts');
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Edit Stripe account' })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Change', exact: true }).click();
  await page.getByRole('button', { name: /Treasury Stripe/ }).click();
  await page.getByRole('button', { name: 'Request withdrawal' }).click();
  await expect(page.getByText('Platform treasury withdrawal request created')).toBeVisible();
  await expect.poll(() => withdrawalPayload).not.toBeNull();
  expect(withdrawalPayload).toEqual({
    amount: '25.00', payout_method: 'stripe', stripe_destination_id: 92,
  });
  await expect(page.getByText('Stripe Corporate Balance', { exact: false })).toHaveCount(0);
});

test('store suspension controls are only shown to business and technical admins', async ({page}) => {
  const stores = [{
    id: 19,
    name: 'Merchant store',
    username: 'merchant-store',
    status: 'active',
    is_official: false,
    created: '2026-10-01T00:00:00Z',
    updated: '2026-10-01T00:00:00Z',
  }, {
    id: 20,
    name: 'Suspended merchant store',
    username: 'suspended-merchant-store',
    status: 'blocked',
    is_official: false,
    created: '2026-10-01T00:00:00Z',
    updated: '2026-10-01T00:00:00Z',
  }];

  for (const [role, canManage] of [
    ['staff', false],
    ['business admin', true],
    ['technical admin', true],
  ] as const) {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    const user = {
      ...profile,
      is_business_admin: role === 'business admin',
      is_superuser: role === 'technical admin',
    };
    await mockApi(page, user);
    await page.route('**/api/admin/staff/stores**', route =>
      route.fulfill({ json: { count: stores.length, results: stores } })
    );

    await page.goto('/admin/stores');
    await expect(page.locator('a[href="/admin/stores/19"]')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Suspend' })).toHaveCount(canManage ? 1 : 0);
    await expect(page.getByRole('button', { name: 'Reactivate' })).toHaveCount(canManage ? 1 : 0);
  }
});

test('store detail provides suspension controls and centers its loading state', async ({ page }) => {
  await mockApi(page, { ...profile, is_business_admin: true });
  let status = 'active';
  let suspensionReason = '';
  await page.route('**/api/admin/staff/stores/44**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (route.request().method() === 'POST') {
      if (path.endsWith('/block')) {
        status = 'blocked';
        const requestBody = route.request().postDataJSON() as { reason: string };
        suspensionReason = requestBody.reason;
      } else if (path.endsWith('/unblock')) {
        status = 'active';
      }
      return route.fulfill({ json: { detail: 'Store status updated' } });
    }
    if (path.endsWith('/products')) return route.fulfill({ json: { count: 0, results: [] } });
    await new Promise(resolve => setTimeout(resolve, 1000));
    return route.fulfill({ json: {
      id: 44,
      name: 'Audit store',
      username: 'audit-store',
      status,
      is_official: false,
      created: '2026-10-01T00:00:00Z',
      updated: '2026-10-01T00:00:00Z',
    } });
  });

  await page.goto('/admin/stores/44');
  const pageLoader = page.locator('.loading.full-page');
  await expect(pageLoader).toBeVisible();
  const loaderBox = await pageLoader.boundingBox();
  const viewport = page.viewportSize();
  expect(loaderBox).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(Math.abs(loaderBox!.x + loaderBox!.width / 2 - viewport!.width / 2)).toBeLessThan(2);
  expect(Math.abs(loaderBox!.y + loaderBox!.height / 2 - viewport!.height / 2)).toBeLessThan(2);

  await expect(page.getByRole('button', { name: 'Suspend store' })).toBeVisible();
  await page.getByRole('button', { name: 'Suspend store' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Reason for suspension').fill('Policy review required.');
  await dialog.getByRole('button', { name: 'Suspend store', exact: true }).click();
  await expect.poll(() => status).toBe('blocked');
  expect(suspensionReason).toBe('Policy review required.');
  await expect(page.getByRole('button', { name: 'Reactivate store' })).toBeVisible();
  await page.getByRole('button', { name: 'Reactivate store' }).click();
  await expect.poll(() => status).toBe('active');
  await expect(page.getByRole('button', { name: 'Suspend store' })).toBeVisible();
});

test('store catalog audit shows sales and links products to read-only preview', async ({page}) => {
  await mockApi(page, { ...profile, is_business_admin: true });
  await page.route('**/api/admin/staff/stores/44**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path.endsWith('/products')) {
      return route.fulfill({ json: { count: 2, results: [
        {
          id: 321,
          title: 'Tracked product',
          category: 'books',
          price: '12.00',
          sales: 17,
          visibility: true,
          is_digital: false,
          has_digital_asset: false,
          available: 20,
          created: '2026-10-01T00:00:00Z',
          product_type: 'standard',
        },
        {
          id: 322,
          title: 'Partner offer',
          category: 'books',
          price: '8.00',
          sales: 0,
          visibility: true,
          is_digital: true,
          has_digital_asset: false,
          available: null,
          created: '2026-10-01T00:00:00Z',
          product_type: 'affiliate_clickbank',
          affiliate_hoplink: 'https://partner.example/offer',
        },
      ] } });
    }
    return route.fulfill({ json: {
      id: 44,
      name: 'Audit store',
      username: 'audit-store',
      status: 'active',
      created: '2026-10-01T00:00:00Z',
      updated: '2026-10-01T00:00:00Z',
    } });
  });

  await page.goto('/admin/stores/44');
  await expect(page.getByRole('columnheader', { name: 'Units sold' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Tracked product' })).toHaveAttribute('href', '/products/321?preview=1');
  await expect(page.getByRole('row', { name: /Tracked product/ })).toContainText('17');
  await expect(page.getByRole('row', { name: /Partner offer/ })).toContainText('Not tracked');
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

test('staff identity opens that staff member’s profile', async ({page}) => {
  await mockApi(page, { ...profile, is_business_admin: true });
  const staffUser = {
    ...profile,
    id: 12,
    first_name: 'Casey',
    last_name: 'Staff',
    role: 'staff',
    gender: 'female',
    is_active: true,
    staff_email_verified: true,
    date_joined: '2026-10-01T09:00:00Z',
    phone1: '+15555550123',
  };
  await page.route('**/api/admin/staff{,/**,?*}', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/admin/staff') {
      return route.fulfill({ json: { count: 1, results: [staffUser] } });
    }
    if (path === '/api/admin/staff/users/12') {
      return route.fulfill({ json: {
        user: staffUser,
        wallet: { count: 0, balance: '0.00', transactions: [] },
        total_orders: 0,
        lifetime_spent: '0.00',
        orders: [],
        activity: [],
      } });
    }
    return route.fulfill({ json: {} });
  });

  await page.goto('/admin/staff');
  const profileLink = page.getByRole('link', { name: 'View profile of Casey Staff' });
  await expect(profileLink).toHaveAttribute('href', '/admin/users/12');
  await profileLink.click();
  await expect(page).toHaveURL(/\/admin\/users\/12$/);
  await expect(page.getByRole('heading', { name: 'Casey Staff' })).toBeVisible();
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
    if (path.endsWith('/payouts')) return route.fulfill({json: {count: 1, results: [{id: 9, reference: 'PAY-9', store: 1, store_name: 'Store one', amount: '12.50', status: 'pending', payout_method: 'bank_transfer', account_details: {}, created: '2026-10-01'}]}});
    return route.fulfill({json: {count: 0, results: []}});
  });
  page.on('dialog', dialog => dialog.accept(dialog.type() === 'prompt' ? 'Verified by support after merchant phone confirmation.' : undefined));
  await page.goto('/admin');
  await expect(page.getByRole('img', {name: 'Order status chart'})).toBeVisible();
  const inspectDetails = async (label: string, title: string): Promise<void> => {
    await page.getByRole('button', { name: label }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: title })).toBeVisible();
    await dialog.getByRole('button', { name: 'Close details' }).click();
  };
  await inspectDetails('View payout PAY-9 details', 'Payout PAY-9');
  await expect(page.getByRole('link', { name: 'Store one' })).toHaveAttribute('href', '/admin/stores/1');
  await inspectDetails('View details for order ORDER44', 'Order #ORDER44');
  await inspectDetails('View details for coupon SAVE10', 'Coupon SAVE10');
  await inspectDetails('View details for refund 7', 'Refund #7');
  await inspectDetails('View order 44 details', 'Order #ORDER44');
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

test('refund order reference opens the order details popup', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ json: profile });
    if (path === '/api/admin/staff/refunds') {
      return route.fulfill({
        json: {
          count: 1,
          results: [{
            id: 7,
            email: 'buyer@test.com',
            order: 44,
            reason: 'Parcel never arrived',
            refund_type: 'store_credit',
            accepted: false,
            status: 'pending',
            created: '2026-10-01T00:00:00Z',
          }],
        },
      });
    }
    if (path === '/api/orders/44') {
      return route.fulfill({
        json: {
          id: 44,
          reference: 'ORDER44',
          status: 'confirmed',
          created: '2026-10-01T00:00:00Z',
          updated: '2026-10-01T00:00:00Z',
          total: '25.00',
          paid_total: '25.00',
          refunded_total: '0.00',
          subtotal: '25.00',
          payment_type: 'card',
          items: [],
          fulfillments: [],
          address: {},
        },
      });
    }
    if (path.includes('notifications')) {
      return route.fulfill({ json: { unread: 0, total: 0 } });
    }
    return route.fulfill({ json: {} });
  });

  await page.goto('/admin/refunds');
  await page.getByRole('button', { name: 'View order 44 details' }).click();
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'Order #ORDER44' })).toBeVisible();
  await expect(page).toHaveURL(/\/admin\/refunds$/);
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

for (const theme of ['light', 'dark']) {
  test(`payout details remain available to staff in ${theme} mode`, async ({page}) => {
    await mockApi(page);
    await page.addInitScript((value: string) => localStorage.setItem('proace-theme', value), theme);
    await page.route(/\/api\/admin\/staff\/payouts(?:\?|$)/, route => route.fulfill({json: {
      count: 1,
      results: [{
        id: 42, reference: 'PAY-DETAIL-42', store: 1, store_name: 'Test store',
        amount: '125.00', status: 'completed', payout_method: 'bank_transfer',
        account_details: {bank_name: 'Test bank', account_number: '1234567890'},
        notes: 'Transfer verified', created: '2026-10-01T09:00:00Z',
        processed_at: '2026-10-02T10:00:00Z',
      }],
    }}));
    await page.goto('/admin/payouts');
    await page.getByRole('button', {name: 'View payout PAY-DETAIL-42 details'}).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', {name: 'Payout PAY-DETAIL-42'})).toBeVisible();
    await expect(dialog.getByText('Test bank', {exact: true})).toBeVisible();
    await expect(dialog.getByText('Transfer verified', {exact: true})).toBeVisible();
    await expect(dialog.getByText('********7890', {exact: true})).toBeVisible();
    await expect(dialog.getByText('1234567890', {exact: true})).toHaveCount(0);
    await expect(page.getByRole('button', {name: 'Approve', exact: true})).toHaveCount(0);
    await dialog.getByRole('button', {name: 'Done', exact: true}).click();
    await expect(dialog).toHaveCount(0);
  });
}

test('staff can decline a pending payout from its details', async ({page}) => {
  await mockApi(page);
  let submitted: Record<string, unknown> | undefined;
  await page.route(/\/api\/admin\/staff\/payouts(?:\/42\/process|\?|$)/, async route => {
    if (route.request().method() === 'POST') {
      submitted = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({json: {detail: 'Payout declined'}});
    }
    return route.fulfill({json: {count: 1, results: [{
      id: 42, reference: 'PAY-PENDING', amount: '25.00', status: 'pending',
      payout_method: 'bank_transfer', account_details: {account_last4: '5676'},
      created: '2026-10-01T09:00:00Z',
    }]}});
  });
  await page.goto('/admin/payouts');
  await page.getByRole('button', {name: 'View payout PAY-PENDING details'}).click();
  const details = page.getByRole('dialog');
  await expect(details.getByText('********76', {exact: true})).toBeVisible();
  await expect(details.getByRole('button', {name: 'Mark paid', exact: true})).toBeVisible();
  await details.getByRole('button', {name: 'Decline', exact: true}).click();
  const confirmation = page.getByRole('dialog');
  await confirmation.getByLabel('Reason for rejection').fill('Account needs verification');
  await confirmation.getByRole('button', {name: 'Reject payout', exact: true}).click();
  await expect.poll(() => submitted?.action).toBe('reject');
  expect(submitted?.reason).toBe('Account needs verification');
});

test('treasury bank picker exposes saved accounts without a default and keeps management in empty Stripe picker', async ({page}, testInfo) => {
  await mockApi(page, {...profile, is_business_admin: true});
  await page.route('**/api/admin/staff/commission-wallet*', route => route.fulfill({json: {
    earned: '100.00', available: '100.00', withdrawn_or_pending: '0.00', withdrawals: [],
  }}));
  await page.route('**/api/bank-accounts*', route => route.fulfill({json: [{
    id: 81, bank_name: 'Kuda Bank', account_holder_name: 'Taylor Staff',
    account_last4: '7890', routing_last4: '2345', is_default: false,
  }]}));
  await page.route('**/api/stripe-payout-destinations*', route => route.fulfill({json: []}));
  await page.goto('/admin/commission');
  await page.getByLabel('Payout method').selectOption('bank');
  await page.getByRole('button', {name: 'Choose account'}).click();
  const bankPicker = page.getByRole('dialog', {name: 'Select bank account'});
  await expect(bankPicker.getByRole('button', {name: 'Edit', exact: true})).toBeVisible();
  await expect(bankPicker.getByRole('button', {name: 'Set default', exact: true})).toBeVisible();
  await expect(bankPicker.getByRole('link', {name: 'Manage payout accounts'})).toBeVisible();
  for (const theme of ['light', 'dark']) {
    await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
    await bankPicker.screenshot({path: testInfo.outputPath(`bank-picker-${theme}.png`)});
  }
  await bankPicker.getByRole('button', {name: /Kuda Bank/}).click();
  await expect(page.getByText('Kuda Bank', {exact: true})).toBeVisible();
  await page.getByLabel('Payout method').selectOption('stripe');
  await page.getByRole('button', {name: 'Choose account'}).click();
  const stripePicker = page.getByRole('dialog', {name: 'Select Stripe account'});
  await expect(stripePicker.getByText('No saved accounts yet. Add one below.')).toBeVisible();
  await expect(stripePicker.getByRole('link', {name: 'Manage payout accounts'})).toBeVisible();
  await stripePicker.screenshot({path: testInfo.outputPath('stripe-empty-picker.png')});
});

test('treasury withdrawal references expose a preview and printable details', async ({page}) => {
  await mockApi(page, {...profile, is_business_admin: true});
  await page.route('**/api/bank-accounts*', route => route.fulfill({json: []}));
  await page.route('**/api/stripe-payout-destinations*', route => route.fulfill({json: []}));
  await page.addInitScript(() => { window.print = () => { document.documentElement.dataset.printed = 'true'; }; });
  await page.route('**/api/admin/staff/commission-wallet*', route => route.fulfill({json: {
    earned: '100.00', available: '75.00', withdrawn_or_pending: '25.00', withdrawal_count: 1,
    withdrawals: [{id: 1, reference: 'PCW-details', amount: '25.00', payout_method: 'bank', status: 'completed', created: '2026-10-14T10:00:00Z', processed_at: null, processing_note: 'Transfer confirmed'}],
  }}));
  await page.goto('/admin/commission');
  const reference = page.getByRole('button', {name: 'PCW-details', exact: true});
  await reference.hover();
  await expect(page.getByRole('tooltip')).toContainText('$25.00');
  await reference.click();
  const dialog = page.getByRole('dialog', {name: 'Withdrawal PCW-details'});
  await expect(dialog).toContainText('Transfer confirmed');
  await dialog.getByRole('button', {name: 'Print details'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-printed', 'true');
});
