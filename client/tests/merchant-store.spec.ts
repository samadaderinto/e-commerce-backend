import { expect, test } from '@playwright/test';

test('active store survives merchant navigation and reloads, and switching resets order filters', async ({ page }) => {
  let trackingPayload: unknown;
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/$/, '');
    let json: unknown = {};
    if (path === '/api/me') json = { id: 7, first_name: 'Seller', email: 'seller@test.com' };
    else if (path === '/api/stores') json = { count: 2, results: [
      { id: 1, name: 'Empty store', status: 'approved' },
      { id: 2, name: 'Busy store', status: 'approved' },
    ] };
    else if (/\/tracking$/.test(path)) trackingPayload = route.request().postDataJSON();
    else if (/\/orders$/.test(path)) {
      const results = path === '/api/stores/2/orders' ? [{
        id: 20, reference: 'BUSY-ORDER', status: 'confirmed', created: '2026-10-01',
        items: [{ product: 30, title: 'Test product', quantity: 1 }],
      }] : [];
      json = { count: results.length, results };
    } else if (/\/products$/.test(path)) json = { count: 0, results: [] };
    else if (path === '/api/cart') json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    else if (path === '/api/wishlist' || path.includes('notifications')) json = [];
    await route.fulfill({ json });
  });
  await page.goto('/merchant/orders');
  await page.getByRole('combobox', { name: 'Select store' }).selectOption('2');
  await expect(page.getByText('BUSY-ORDER', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ship / Track' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel('Shipping Carrier')).toHaveValue('USPS');
  for (const carrier of ['UPS', 'FedEx', 'DHL']) {
    await expect(dialog.locator(`option[value="${carrier}"]`)).toHaveJSProperty('disabled', false);
  }
  await dialog.getByLabel('Order Tracking Number').fill('9400100000000000000000');
  await dialog.getByLabel('Order Status').selectOption('shipped');
  await dialog.getByRole('button', { name: 'Save tracking & notify customer' }).click();
  await expect(dialog).not.toBeVisible();
  expect(trackingPayload).toEqual({ carrier: 'USPS', tracking_number: '9400100000000000000000', status: 'shipped' });
  await page.locator('.merchant-sidebar').getByRole('link', { name: 'Products', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Select store' })).toHaveValue('2');
  await expect(page.getByRole('link', { name: 'View storefront' })).toHaveAttribute('href', '/shop?store=2');
  await page.locator('.merchant-sidebar').getByRole('link', { name: 'Store settings' }).click();
  await expect(page.getByRole('combobox', { name: 'Select store' })).toHaveValue('2');
  await page.locator('.merchant-sidebar').getByRole('link', { name: 'Orders', exact: true }).click();
  await expect(page.getByText('BUSY-ORDER', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('combobox', { name: 'Select store' })).toHaveValue('2');
  await expect(page.getByText('BUSY-ORDER', { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Filter orders by status' }).selectOption('delivered');
  await page.getByRole('combobox', { name: 'Select store' }).selectOption('1');
  await expect(page.getByRole('combobox', { name: 'Filter orders by status' })).toHaveValue('');
  await expect(page.getByText('Your customer orders will appear here.')).toBeVisible();
});

test('a product outside the selected store explains the store boundary', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') {
      await route.fulfill({ json: { id: 7, first_name: 'Admin', email: 'admin@test.com', is_staff: true } });
      return;
    }
    if (path === '/api/stores') {
      await route.fulfill({ json: { count: 1, results: [{ id: 1, name: 'Official store', status: 'active', is_official: true }] } });
      return;
    }
    if (path === '/api/stores/1/products/365') {
      await route.fulfill({ status: 404, json: { detail: 'No Product matches the given query.' } });
      return;
    }
    if (path === '/api/cart') {
      await route.fulfill({ json: { items: [], subtotal: '0', shipping: '0', total: '0' } });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.goto('/merchant/products/365');
  await expect(page.getByRole('heading', { name: 'This product is not in the selected store' })).toBeVisible();
  await expect(page.getByText(/manage another seller’s product from Backoffice/)).toBeVisible();
});

test('official-store admin previews an unsaved digital product in a separate page', async ({ page, context }) => {
  let writes: number = 0;
  await context.route('**/api/**', async route => {
    const request = route.request();
    const path: string = new URL(request.url()).pathname.replace(/\/$/, '');
    if (request.method() !== 'GET') writes += 1;
    let json: unknown = {};
    if (path === '/api/me') json = { id: 7, first_name: 'Admin', email: 'admin@test.com', is_staff: true, is_superuser: true };
    else if (path === '/api/stores') json = { count: 1, results: [{ id: 1, name: 'Official store', status: 'active', is_official: true }] };
    else if (path === '/api/cart') json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    else if (path === '/api/wishlist' || path.includes('notifications')) json = [];
    await route.fulfill({ json });
  });
  await page.goto('/merchant/products/new');
  await page.locator('input[name="title"]').fill('Official digital guide');
  await page.locator('textarea[name="description"]').fill('A downloadable guide.');
  await page.locator('input[name="price"]').fill('25.00');
  await page.locator('input[name="is_digital"]').check();
  const popupPromise = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  const preview = await popupPromise;
  await expect(preview).toHaveURL(/\/merchant\/products\/preview$/);
  await expect(preview.getByRole('heading', { name: 'Official digital guide' })).toBeVisible({ timeout: 30000 });
  await expect(preview.getByText('Instant digital download', { exact: true })).toBeVisible();
  await expect(preview.getByRole('button', { name: 'Add to bag' })).toBeDisabled();
  await expect(page.locator('input[name="title"]')).toHaveValue('Official digital guide');
  expect(writes).toBe(0);
  await preview.close();
});

test('retrying a failed cover upload updates the saved product without creating another listing', async ({ page, context }) => {
  const mutations: { path: string; method: string }[] = [];
  let uploads: number = 0;
  let product: Record<string, unknown> = {
    id: 42, title: 'Original product', description: 'A product description.', category: 'electronics',
    brand: '', price: '25.00', discount: 0, available: 0, visibility: false, weight: '1.00',
    length: '10.00', width: '8.00', height: '4.00', is_digital: false,
    image_url: '', digital_file_url: '', images: [], variants: [], tags: [], specifications: [],
  };
  await context.route('**/api/**', async route => {
    const request = route.request();
    const path: string = new URL(request.url()).pathname.replace(/\/$/, '');
    const method: string = request.method();
    let json: unknown = {};
    if (path === '/api/me') json = { id: 7, first_name: 'Admin', email: 'admin@test.com', is_staff: true, is_superuser: true };
    else if (path === '/api/stores') json = { count: 1, results: [{ id: 1, name: 'Official store', status: 'active', is_official: true }] };
    else if (path === '/api/stores/1/products' && method === 'POST') {
      mutations.push({ path, method });
      product = { ...product, ...request.postDataJSON() as Record<string, unknown> };
      json = product;
    } else if (path === '/api/stores/1/products/42') {
      if (method === 'PATCH') {
        mutations.push({ path, method });
        product = { ...product, ...request.postDataJSON() as Record<string, unknown> };
      }
      json = product;
    } else if (path === '/api/stores/1/products/42/images' && method === 'POST') {
      uploads += 1;
      if (uploads === 1) { await route.fulfill({ status: 500, json: { detail: 'Upload directory is not writable.' } }); return; }
      json = { id: 8, image: '/cover.png' };
    } else if (path === '/api/cart') json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    else if (path === '/api/wishlist' || path.includes('notifications')) json = [];
    await route.fulfill({ json });
  });
  await page.goto('/merchant/products/new');
  await page.locator('input[name="title"]').fill('Original product');
  await page.locator('textarea[name="description"]').fill('A product description.');
  await page.locator('select[name="category"]').selectOption('electronics');
  await page.locator('input[name="price"]').fill('25.00');
  await page.locator('.product-editor input[type="file"]').setInputFiles({
    name: 'cover.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX3sAAAAASUVORK5CYII=', 'base64'),
  });
  await page.getByRole('button', { name: 'Create product', exact: true }).click();
  await expect(page.getByText(/Your product is saved, but this step failed/)).toBeVisible();
  await page.locator('input[name="title"]').fill('Updated product');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page).toHaveURL(/\/merchant\/products\/42$/);
  await expect(page.locator('input[name="title"]')).toHaveValue('Updated product');
  expect(mutations).toEqual([
    { path: '/api/stores/1/products', method: 'POST' },
    { path: '/api/stores/1/products/42', method: 'PATCH' },
  ]);
  expect(uploads).toBe(2);
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect.poll(() => mutations.length).toBe(3);
  expect(mutations[2]).toEqual({ path: '/api/stores/1/products/42', method: 'PATCH' });
  expect(uploads).toBe(2);
});

test('onboarding preview includes unsaved variants and a flash deal', async ({ page, context }) => {
  let writes: number = 0;
  await context.route('**/api/**', async route => {
    const request = route.request();
    const path: string = new URL(request.url()).pathname.replace(/\/$/, '');
    if (request.method() !== 'GET') writes += 1;
    let json: unknown = {};
    if (path === '/api/me') json = { id: 7, first_name: 'Admin', email: 'admin@test.com', is_staff: true, is_superuser: true };
    else if (path === '/api/stores') json = { count: 1, results: [{ id: 1, name: 'Official store', status: 'active', is_official: true }] };
    else if (path === '/api/cart') json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    else if (path === '/api/wishlist' || path.includes('notifications')) json = [];
    await route.fulfill({ json });
  });
  await page.goto('/merchant/products/new');
  await page.locator('input[name="title"]').fill('Onboarding shirt');
  await page.locator('textarea[name="description"]').fill('A shirt with options.');
  await page.locator('input[name="price"]').fill('25.00');
  await page.locator('input[name="discount"]').fill('20');
  await page.locator('input[name="flash_sale_end"]').fill('2099-12-31T23:59');
  await page.getByRole('button', { name: 'Add variant' }).click();
  await page.getByPlaceholder('e.g. Black / Large').fill('Blue / Large');
  await page.locator('.variant-card input[type="number"]').first().fill('5');
  const popupPromise = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  const preview = await popupPromise;
  await expect(preview).toHaveURL(/\/merchant\/products\/preview$/);
  await expect(preview.getByRole('heading', { name: 'Onboarding shirt' })).toBeVisible({ timeout: 30000 });
  await expect(preview.getByRole('button', { name: /Blue \/ Large/ })).toBeVisible();
  await expect(preview.getByLabel(/Flash deal ends in/)).toBeVisible();
  await expect(preview.getByLabel(/Flash deal ends in/)).toContainText(/\d{2}:\d{2}:\d{2}:\d{2}/);
  await preview.getByRole('button', { name: /Blue \/ Large/ }).click();
  await expect(preview.getByRole('button', { name: /Blue \/ Large/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(preview.locator('.detail-price > strong')).toHaveText('$25.00');
  await expect(preview.getByRole('button', { name: 'Add to bag' })).toBeDisabled();
  await expect(page.locator('input[name="title"]')).toHaveValue('Onboarding shirt');
  expect(writes).toBe(0);
  await preview.close();
});


test('ClickBank editor hides local promotions and previews vendor-controlled pricing', async ({ page, context }) => {
  await context.route('**/api/**', async route => {
    const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let json: unknown = {};
    if (path === '/api/me') {
      json = { id: 7, first_name: 'Admin', email: 'admin@test.com', is_staff: true, is_superuser: true };
    } else if (path === '/api/stores') {
      json = { count: 1, results: [{ id: 1, name: 'Official store', status: 'active', is_official: true }] };
    } else if (path === '/api/cart') {
      json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    } else if (path === '/api/wishlist' || path.includes('notifications')) {
      json = [];
    }
    await route.fulfill({ json });
  });
  await page.goto('/merchant/products/new');
  await page.locator('input[name="title"]').fill('Partner guide');
  await page.locator('textarea[name="description"]').fill('A guide sold by the partner.');
  await page.locator('input[name="price"]').fill('25.00');
  await page.locator('input[name="discount"]').fill('20');
  await page.locator('input[name="flash_sale_end"]').fill('2030-10-10T12:00');
  await page.locator('select[name="product_type"]').selectOption('affiliate_clickbank');
  await expect(page.locator('input[name="discount"][type="number"]')).toHaveCount(0);
  await expect(page.locator('input[name="flash_sale_end"]')).toHaveCount(0);
  await expect(page.locator('input[name="discount"][type="hidden"]')).toHaveValue('0');
  const popupPromise = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  const preview = await popupPromise;
  await expect(preview.getByRole('heading', { name: 'Partner guide' })).toBeVisible({ timeout: 30000 });
  await expect(preview.getByText('Price available on partner site', { exact: true })).toBeVisible();
  await expect(preview.locator('.detail-price del')).toHaveCount(0);
  await expect(preview.locator('.flash-deal-badge')).toHaveCount(0);
  await preview.close();
});
