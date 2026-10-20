import { expect, test, type Page, type Route } from '@playwright/test';
import type { NotificationItem } from '../src/lib/types';
import { postAuthWithRetry } from './helpers/auth';

type Profile = {
  id: number;
  first_name: string;
  email: string;
  is_staff: boolean;
  is_superuser: boolean;
  is_business_admin: boolean;
};

const profiles: Profile[] = [
  'shopper', 'buyer', 'seller', 'merchant', 'staff', 'business-admin', 'admin',
].map((name, index) => ({
  id: index + 1,
  first_name: name,
  email: `${name}@test.com`,
  is_staff: ['staff', 'business-admin', 'admin'].includes(name),
  is_superuser: name === 'admin',
  is_business_admin: name === 'business-admin',
}));

async function mockProfile(page: Page, profile?: Profile): Promise<void> {
  await page.route('**/api/**', async (route: Route): Promise<void> => {
    const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let json: unknown = { count: 0, results: [], pages: 1 };
    if (path === '/api/me') {
      await route.fulfill({ status: profile ? 200 : 401, json: profile || { detail: 'Sign in' } });
      return;
    }
    if (path === '/api/cart') json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    if (path === '/api/wishlist') json = [];
    if (path.includes('notifications/counts')) json = { unread: 1, read: 0, archived: 0, total: 1 };
    if (path === '/api/stores') json = {
      count: 1,
      results: [{ id: 1, name: 'Test store', status: 'active', is_official: true }],
    };
    if (path === '/api/stores/1') json = { id: 1, name: 'Test store', status: 'active', is_official: true };
    await route.fulfill({ json });
  });
}

async function assertStableControl(
  page: Page,
  label: string,
  option: string,
): Promise<void> {
  const control = page.getByRole('combobox', { name: label, exact: true });
  const original = await control.elementHandle();
  if (!original) throw new Error(`Missing ${label}`);
  const content = page.locator('.empty-state').first();
  const initialContentBox = await content.count() ? await content.boundingBox() : null;
  await control.selectOption(option);
  await expect(page.locator('.loading.compact').first()).toBeVisible();
  if (initialContentBox) {
    expect((await content.boundingBox())?.y).toBeCloseTo(initialContentBox.y, 0);
  }
  expect(await original.evaluate(element => element.isConnected)).toBe(true);
  await expect(control).toHaveValue(option);
}

for (const profile of profiles) {
  test(`${profile.first_name}: notification search retains results and focus`, async ({ page }) => {
    await mockProfile(page, profile);
    const item: NotificationItem = {
      id: 1, level: 'info', unread: true, verb: 'Existing notice',
      timestamp: '2026-10-10T00:00:00Z', deleted: false, category: 'order',
      data: { url: '/orders/1', order_id: 1 },
    };
    await page.route('**/api/notifications/filters', async route => {
      await route.fulfill({ json: {
        categories: [{ id: 'all', label: 'All Categories', count: 1 }], stores: [],
        counts: { unread: 1, read: 0, archived: 0, total: 1 },
      } });
    });
    let release: (() => void) | undefined;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route(/\/api\/notifications\?/, async route => {
      const filtered: boolean = new URL(route.request().url()).searchParams.has('search');
      if (filtered) await pending;
      await route.fulfill({ json: { count: 1, results: [{ ...item, verb: filtered ? 'Matching notice' : item.verb }] } });
    });
    await page.goto('/notifications');
    await expect(page.getByRole('heading', { name: 'Existing notice' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'View order' })).toHaveAttribute('href', '/orders/1');
    const input = page.getByPlaceholder('Search notifications by keyword, reference, order…');
    try {
      await input.fill('matching');
      await expect(page.locator('.loading.compact')).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Existing notice' })).toBeVisible();
      await expect(input).toBeFocused();
      release?.();
      await expect(page.getByRole('heading', { name: 'Matching notice' })).toBeVisible();
    } finally {
      release?.();
    }
  });
}

for (const profile of [undefined, ...profiles.filter(profile => !profile.is_staff)]) {
  test(`${profile?.first_name || 'guest'}: shop sort preserves document and browser history`, async ({ page }) => {
    await mockProfile(page, profile);
    let release: (() => void) | undefined;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route(/\/api\/products\?/, async route => {
      if (new URL(route.request().url()).searchParams.get('ordering') === 'price') await pending;
      await route.fulfill({ json: { count: 0, pages: 1, results: [] } });
    });
    await page.goto('/shop');
    await expect(page.getByRole('heading', { name: 'No finds just yet' })).toBeVisible();
    let navigations: number = 0;
    page.on('request', request => {
      if (request.isNavigationRequest() && request.resourceType() === 'document') navigations += 1;
    });
    try {
      await assertStableControl(page, 'Sort products', 'price');
      await expect(page).toHaveURL(/ordering=price/);
      await expect(page.getByRole('heading', { name: 'No finds just yet' })).toBeVisible();
      release?.();
      await expect(page.locator('.loading.compact')).toHaveCount(0);
      await page.goBack();
      await expect(page.getByRole('combobox', { name: 'Sort products' })).toHaveValue('-created');
      expect(navigations).toBe(0);
    } finally {
      release?.();
    }
  });
}

for (const profile of profiles.filter(profile => profile.is_staff)) {
  test(`${profile.first_name}: backoffice role filter preserves controls`, async ({ page }) => {
    await mockProfile(page, profile);
    const role = profile.is_superuser || profile.is_business_admin ? 'staff' : 'customer';
    let release: (() => void) | undefined;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/api/admin/staff/users?**', async route => {
      if (new URL(route.request().url()).searchParams.get('role') === role) await pending;
      await route.fulfill({ json: { count: 0, results: [] } });
    });
    await page.goto('/admin/users');
    await expect(page.getByText('0 matching records', { exact: true })).toBeVisible();
    try {
      if (role === 'customer') {
        await expect(page.getByRole('combobox', { name: 'users: Role' }).locator('option[value="staff"]')).toHaveCount(0);
        await expect(page.getByRole('combobox', { name: 'users: Role' }).locator('option[value="admin"]')).toHaveCount(0);
      }
      await assertStableControl(page, 'users: Role', role);
      release?.();
      await expect(page.locator('.loading.compact')).toHaveCount(0);
    } finally {
      release?.();
    }
  });
}

for (const profile of profiles.filter(profile => !['shopper', 'buyer'].includes(profile.first_name))) {
  test(`${profile.first_name}: store product sort preserves controls`, async ({ page }) => {
    await mockProfile(page, profile);
    let release: (() => void) | undefined;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/api/stores/1/products?**', async route => {
      if (new URL(route.request().url()).searchParams.get('ordering') === 'created') await pending;
      await route.fulfill({ json: { count: 0, results: [] } });
    });
    await page.goto('/merchant/products');
    await expect(page.getByRole('combobox', { name: 'Sort products' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Drafts', exact: true })).toBeVisible();
    try {
      await assertStableControl(page, 'Sort products', 'created');
      release?.();
      await expect(page.locator('.loading.compact')).toHaveCount(0);
    } finally {
      release?.();
    }
  });
}

for (const profile of profiles.filter(profile => profile.is_staff)) {
  test(`${profile.first_name}: customer detail filters keep the whole profile mounted`, async ({ page }) => {
    await mockProfile(page, profile);
    let release: (() => void) | undefined;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/api/admin/staff/users/99?**', async route => {
      if (new URL(route.request().url()).searchParams.get('order_status') === 'shipped') await pending;
      await route.fulfill({ json: {
        user: {
          id: 99, first_name: 'Test', last_name: 'Customer', email: 'customer@test.com',
          role: 'customer', is_active: true, date_joined: '2026-10-01T00:00:00Z',
        },
        wallet: { balance: '0.00', transactions: [] }, orders: [], activity: [],
      } });
    });
    await page.goto('/admin/users/99');
    await expect(page.getByRole('heading', { name: 'Test Customer', exact: true })).toBeVisible();
    try {
      await assertStableControl(page, 'Filter orders by status', 'shipped');
      await expect(page.getByRole('heading', { name: 'Test Customer', exact: true })).toBeVisible();
      release?.();
      await expect(page.locator('.loading.compact')).toHaveCount(0);
    } finally {
      release?.();
    }
  });
}

for (const profile of profiles) {
  test(`${profile.first_name}: seeded account filters update without a document reload`, async ({ page, baseURL }) => {
    test.setTimeout(150000);
    const login = await postAuthWithRetry(page.request, '/api/auth/login', {
      headers: { origin: new URL(baseURL!).origin },
      data: {
        email: `${profile.first_name}@proace.local`,
        password: profile.is_superuser
          ? process.env.E2E_TECHNICAL_ADMIN_PASSWORD || process.env.E2E_DEMO_PASSWORD || 'ProaceDemo2026!'
          : process.env.E2E_DEMO_PASSWORD || 'ProaceDemo2026!',
      },
    });
    expect(login.ok()).toBe(true);
    const isStoreOwner: boolean = ['seller', 'merchant'].includes(profile.first_name);
    const path: string = profile.is_staff ? '/admin/users' : isStoreOwner ? '/merchant/products' : '/shop';
    const label: string = profile.is_staff ? 'users: Role' : 'Sort products';
    const option: string = profile.is_staff
      ? profile.is_superuser || profile.is_business_admin ? 'staff' : 'customer'
      : isStoreOwner ? 'created' : 'price';
    await page.goto(path);
    const control = page.getByRole('combobox', { name: label, exact: true });
    await expect(control).toBeVisible({ timeout: 30000 });
    await expect(page.locator('main .loading, main [aria-label="Loading products"]')).toHaveCount(0, { timeout: 30000 });
    await expect(page.getByRole('heading', { name: 'Something interrupted your visit' })).toHaveCount(0);
    await expect(page.locator('.loading.compact')).toHaveCount(0);
    let release: (() => void) | undefined;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url());
      const matches: boolean = profile.is_staff
        ? url.pathname.includes('/admin/staff/users') && url.searchParams.get('role') === option
        : url.pathname.includes('/products') && url.searchParams.get('ordering') === option;
      if (matches) await pending;
      await route.continue();
    });
    let documentRequests: number = 0;
    page.on('request', request => {
      if (request.isNavigationRequest() && request.resourceType() === 'document') documentRequests += 1;
    });
    const filteredResponse = page.waitForResponse(response => {
      const url = new URL(response.url());
      return profile.is_staff
        ? url.pathname.includes('/admin/staff/users') && url.searchParams.get('role') === option
        : url.pathname.includes('/products') && url.searchParams.get('ordering') === option;
    }, { timeout: 30000 });
    try {
      await assertStableControl(page, label, option);
      release?.();
      expect((await filteredResponse).ok()).toBe(true);
      await expect(page.locator('.loading.compact')).toHaveCount(0);
      await expect(control).toHaveValue(option);
      expect(documentRequests).toBe(0);
      await expect(page.getByRole('heading', { name: 'Something interrupted your visit' })).toHaveCount(0);
    } finally {
      release?.();
    }
  });
}
