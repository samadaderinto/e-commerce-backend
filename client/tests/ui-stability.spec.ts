import { expect, test } from '@playwright/test';

const product = {
  id: 991,
  title: 'A deliberately long product title for responsive layouts',
  description: 'An everyday item.',
  category: 'electronics',
  price: '10.00',
  sale_price: '10.00',
  discount: 0,
  available: 3,
  store: 1,
  store_name: 'Shop',
  store_username: 'shop',
  average_rating: '0',
  rating_count: 0,
  images: [],
  image: '',
  tags: [],
  is_own_store: false,
  is_digital: false,
};

for (const storageError of ['SecurityError', 'QuotaExceededError']) {
  test(`shopping remains usable when persistence throws ${storageError}`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error: Error) => errors.push(error.message));
    await page.addInitScript((name: string) => {
      Storage.prototype.setItem = (): void => {
        throw new DOMException('Storage unavailable', name);
      };
    }, storageError);
    await page.route('**/api/**', route => {
      const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
      if (path === '/api/me') {
        return route.fulfill({ status: 401, json: { detail: 'Sign in' } });
      }
      if (path === '/api/products/991') return route.fulfill({ json: product });
      if (path === '/api/products') {
        return route.fulfill({ json: { count: 1, pages: 1, results: [product] } });
      }
      return route.fulfill({ json: [] });
    });
    await page.goto('/products/991');
    await page.getByRole('button', { name: 'Add to bag', exact: true }).click();
    await page.locator('a[href="/cart"]').first().click();
    await expect(page.getByRole('link', { name: product.title }).first()).toBeVisible();
    await expect(page.getByText(/This page couldn.t load/)).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test('bounded pagination and stock-limited bag quantities across breakpoints', async ({ page }) => {
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ status: 401, json: { detail: 'Sign in' } });
    if (path === '/api/products/991') return route.fulfill({ json: product });
    if (path === '/api/products') return route.fulfill({ json: { count: 840, pages: 42, results: [product] } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/shop?page=5');
  const navigation = page.getByRole('navigation', { name: 'Pagination' });
  await expect(navigation).toBeVisible();
  expect(await navigation.locator('button').count()).toBeLessThanOrEqual(7);

  for (const width of [360, 390, 430, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }

  await page.goto('/products/991');
  await page.getByRole('button', { name: 'Increase quantity' }).click();
  await page.getByRole('button', { name: 'Add to bag', exact: true }).click();
  await expect
    .poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('proace-cart') || '[]')[0]?.quantity))
    .toBe(2);

  const addButton = page.locator('.purchase-actions').getByRole('button').first();
  await expect(page.getByRole('button', { name: '2 in bag', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Increase quantity' }).click();
  await expect(addButton).toBeEnabled();
  await addButton.click();
  await expect
    .poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('proace-cart') || '[]')[0]?.quantity))
    .toBe(3);
  await expect(page.getByRole('button', { name: 'Max quantity in bag', exact: true })).toBeDisabled();

  await page.reload();
  await expect(page.getByRole('button', { name: 'Max quantity in bag', exact: true })).toBeDisabled();
});

test('lowering product quantity after adding a larger amount stays enabled', async ({ page }) => {
  const stockedProduct = { ...product, available: 12 };
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ status: 401, json: { detail: 'Sign in' } });
    if (path === '/api/products/991') return route.fulfill({ json: stockedProduct });
    if (path === '/api/products') return route.fulfill({ json: { count: 1, pages: 1, results: [stockedProduct] } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/shop?page=1');
  await page.goto('/products/991');
  for (let index = 0; index < 5; index++) {
    await page.getByRole('button', { name: 'Increase quantity' }).click();
  }
  await page.getByRole('button', { name: 'Add to bag', exact: true }).click();
  await expect
    .poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('proace-cart') || '[]')[0]?.quantity))
    .toBe(6);
  await expect(page.getByRole('button', { name: '6 in bag', exact: true })).toBeDisabled();

  for (let index = 0; index < 3; index++) {
    await page.getByRole('button', { name: 'Decrease quantity' }).click();
  }
  await expect(page.getByRole('button', { name: 'Update bag', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Update bag', exact: true }).click();
  await expect
    .poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('proace-cart') || '[]')[0]?.quantity))
    .toBe(3);
  await expect(page.getByRole('button', { name: '3 in bag', exact: true })).toBeDisabled();
});

test('product page copy control copies the link without opening native sharing', async ({ page }) => {
  await page.addInitScript(() => {
    const testWindow = window as Window & {
      __shareCalls: number;
      __copiedProductUrl: string;
    };
    testWindow.__shareCalls = 0;
    testWindow.__copiedProductUrl = '';
    Object.defineProperty(navigator, 'share', {
      configurable: true,
      value: async () => {
        testWindow.__shareCalls += 1;
      },
    });
    Object.defineProperty(navigator, 'canShare', {
      configurable: true,
      value: () => true,
    });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          testWindow.__copiedProductUrl = value;
        },
      },
    });
  });
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ status: 401, json: { detail: 'Sign in' } });
    if (path === '/api/products/991') return route.fulfill({ json: product });
    if (path === '/api/products') return route.fulfill({ json: { count: 1, pages: 1, results: [product] } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/shop?page=1');
  await page.goto('/products/991');
  const copyButton = page.getByRole('button', { name: 'Share product' });
  await copyButton.click();

  await expect(copyButton).toHaveAttribute('title', 'Link copied!');
  const copiedUrl = await page.evaluate(
    () => (window as Window & { __copiedProductUrl: string }).__copiedProductUrl,
  );
  expect(copiedUrl).toBe(new URL('/products/991', page.url()).href);
  const shareCalls = await page.evaluate(
    () => (window as Window & { __shareCalls: number }).__shareCalls,
  );
  expect(shareCalls).toBe(0);
});

test('four carriers switch plans and totals', async ({ page }) => {
  const requests: string[] = [];

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === '/api/me') {
      return route.fulfill({ json: { id: 7, first_name: 'Taylor', email: 'buyer@test.com' } });
    }
    if (path === '/api/cart') {
      return route.fulfill({
        json: {
          items: [{ product, quantity: 1, total: '10', purchasable: true }],
          subtotal: '10',
          shipping: '2',
          total: '12',
        },
      });
    }
    if (path === '/api/addresses') {
      return route.fulfill({
        json: [
          {
            id: 1,
            address: '1 Main St',
            city: 'Austin',
            state: 'TX',
            country: 'US',
            zip: '78701',
            is_default: true,
          },
        ],
      });
    }
    if (path === '/api/wallet') {
      return route.fulfill({ json: { balance: '100' } });
    }
    if (path === '/api/checkout/shipping-rates') {
      const carrier = url.searchParams.get('carrier') || 'USPS';
      requests.push(carrier);
      return route.fulfill({
        json: [
          {
            carrier,
            service_id: `${carrier}_ground`,
            name: `${carrier} Ground`,
            amount: String(['UPS', 'FEDEX', 'DHL', 'USPS'].indexOf(carrier) + 4),
            tax: '1',
            description: 'Tracked delivery',
            quote_token: `quote-${carrier}`,
          },
        ],
      });
    }
    if (path.includes('notifications/stream')) {
      return route.fulfill({ status: 503, json: { detail: 'Offline' } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto('/checkout');
  await expect(page.locator('.carrier-options input[type=radio]')).toHaveCount(4);

  for (const carrier of ['UPS', 'FEDEX', 'DHL', 'USPS']) {
    await page.locator(`input[name="shipping-carrier"][value="${carrier}"]`).check();
    await expect(page.getByText(`${carrier} Ground`, { exact: false }).first()).toBeVisible();
    await expect(page.locator('input[name="shipping_service"]')).toBeChecked();
    expect(requests).toContain(carrier);
    await expect(page.locator('.summary-total strong')).toHaveText(
      `$${(15 + ['UPS', 'FEDEX', 'DHL', 'USPS'].indexOf(carrier)).toFixed(2)}`
    );
  }

  for (const width of [360, 430, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
});

test('live notification frames refresh queries and show an operator toast', async ({ page }) => {
  let reads = 0;

  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/me') {
      return route.fulfill({
        json: { id: 7, first_name: 'Taylor', email: 'staff@test.com', is_staff: true },
      });
    }
    if (path === '/api/notifications/stream') {
      const eventStream = [
        'event: ready',
        'data: {"resync":true}',
        '',
        'event: state',
        'data: {"event":"notification.created","notification_id":42,"title":"Live stock alert","data":{"event":"inventory_low"}}',
        '',
        '',
      ].join('\n');
      return route.fulfill({ contentType: 'text/event-stream', body: eventStream });
    }
    if (path === '/api/notifications/counts') {
      reads++;
      return route.fulfill({ json: { unread: reads, total: reads } });
    }
    return route.fulfill({ json: { count: 0, results: [], next: null } });
  });

  await page.goto('/settings');
  await expect(page.getByRole('status').filter({ hasText: 'Live stock alert' })).toBeVisible();
  await expect.poll(() => reads).toBeGreaterThan(1);
});
