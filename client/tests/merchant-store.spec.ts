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
