import { expect, test, type Page } from '@playwright/test';
import type { OrderFulfillment } from '../src/lib/types';

async function mockOrder(
  page: Page,
  status: () => string,
  digital: boolean = false,
  fulfillments: OrderFulfillment[] = [],
): Promise<void> {
  await page.route('**/api/**', async route => {
    const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let json: unknown = { count: 0, results: [] };
    if (path === '/api/me') {
      json = { id: 7, first_name: 'Customer', email: 'customer@test.com' };
    } else if (path === '/api/orders/1') {
      const currentStatus: string = status();
      json = {
        id: 1,
        reference: 'STATE-ORDER',
        status: currentStatus,
        created: new Date().toISOString(),
        status_updated_at: new Date().toISOString(),
        total: '10.00',
        paid_total: currentStatus === 'pending' ? '0.00' : '10.00',
        refunded_total: currentStatus === 'refunded' ? '10.00' : '0.00',
        subtotal: '10.00',
        payment_type: 'User Wallet',
        fulfillments,
        items: [{ product: 1, title: 'Order item', quantity: 1, unit_price: '10.00', is_digital: digital }],
        address: { address: 'Test address', city: 'Test city', state: 'Test state', country: 'US', zip: '10001' },
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
}

for (const status of ['pending', 'confirmed', 'shipped', 'delivered', 'picked up', 'cancelled', 'refunded']) {
  test(`customer order reflects ${status} in both themes`, async ({ page }, testInfo) => {
    await mockOrder(page, () => status);
    await page.goto('/orders/1?placed=1');
    await expect(page.getByRole('heading', { name: 'Order details', exact: true })).toBeVisible();
    if (status === 'pending') await expect(page.getByText(/Awaiting payment/)).toBeVisible();
    if (status === 'refunded') await expect(page.getByText('ProAce Wallet · Refunded', { exact: true })).toBeVisible();
    const terminal: boolean = ['cancelled', 'refunded'].includes(status);
    const tracker = page.getByRole('list', { name: 'Order status tracker' });
    if (terminal) {
      await expect(tracker).toHaveCount(0);
      await expect(page.getByRole('status', { name: 'Order status' })).toContainText(status === 'cancelled' ? 'Cancelled' : 'Refunded');
    } else {
      await expect(tracker.locator('[aria-current="step"]')).toHaveText(new RegExp(status, 'i'));
      if (status === 'pending') {
        await expect(tracker.locator('.done')).toHaveCount(1);
        await expect(page.getByText('Your order STATE-ORDER is confirmed.', { exact: false })).toHaveCount(0);
      }
    }
    await expect(page.getByRole('button', { name: 'Cancel order', exact: true })).toHaveCount(['pending', 'confirmed'].includes(status) ? 1 : 0);
    if (terminal || status === 'pending') {
      await expect(page.getByRole('button', { name: 'Request a return / refund', exact: true })).toHaveCount(0);
    }
    for (const theme of ['light', 'dark']) {
      await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
      await page.screenshot({ path: testInfo.outputPath(`order-${theme}.png`), fullPage: true });
    }
  });
}

test('digital order tracker omits physical shipping', async ({ page }) => {
  await mockOrder(page, () => 'confirmed', true);
  await page.goto('/orders/1');
  const tracker = page.getByRole('list', { name: 'Order status tracker' });
  await expect(tracker).toBeVisible();
  await expect(tracker).not.toContainText('Shipped');
  await expect(page.getByRole('button', { name: 'Cancel order', exact: true })).toHaveCount(0);
});

test('multi-store orders show tracking for each shipment', async ({ page }) => {
  await mockOrder(page, () => 'shipped', false, [
    {
      store: 1,
      store_name: 'First Store',
      status: 'shipped',
      carrier: 'USPS',
      tracking_number: 'TRACK-FIRST',
      shipped_at: new Date().toISOString(),
      delivered_at: null,
    },
    {
      store: 2,
      store_name: 'Second Store',
      status: 'confirmed',
      carrier: 'UPS',
      tracking_number: 'TRACK-SECOND',
      shipped_at: null,
      delivered_at: null,
    },
  ]);
  await page.goto('/orders/1');

  await expect(page.getByText('Delivery updates by store')).toBeVisible();
  await expect(page.getByText('First Store')).toBeVisible();
  await expect(page.getByText('Second Store')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Track shipment' })).toHaveCount(2);
});

test('staff status changes refresh the active customer order', async ({ page }) => {
  let status: string = 'confirmed';
  await mockOrder(page, () => status);
  await page.goto('/orders/1');
  await expect(page.getByRole('list', { name: 'Order status tracker' })).toBeVisible();
  status = 'cancelled';
  await expect(page.getByRole('status', { name: 'Order status' })).toContainText('Cancelled', { timeout: 25000 });
  await expect(page.getByRole('button', { name: 'Cancel order', exact: true })).toHaveCount(0);
});
