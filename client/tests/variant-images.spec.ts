import { test, expect } from '@playwright/test';

test('selecting a mapped variant activates its photo and preserves carousel navigation', async ({ page }) => {
  const origin = 'http://127.0.0.1:3000';
  const cover = `${origin}/variant-photos/black.svg`;
  const blue = `${origin}/variant-photos/blue.svg`;
  const product = {
    id: 991, title: 'Variant photo test', description: 'A shirt with color options.',
    category: 'outwear', brand: 'Demo', price: '100.00', sale_price: '100.00',
    discount: 0, available: 20, store: 1, store_name: 'Demo', store_username: 'demo',
    average_rating: '0', rating_count: 0, sales: 0, images: [cover, blue], image: cover,
    tags: [], created: '2026-10-05T00:00:00Z', is_own_store: false, is_digital: false,
    variants: [
      { name: 'Black', price_delta: '0.00', available: 10, image_url: cover },
      { name: 'Blue', price_delta: '23.00', available: 10, image_url: blue },
      { name: 'Blue / Large', price_delta: '25.00', available: 5, image_url: blue },
      { name: 'No mapped photo', price_delta: '0.00', available: 5 },
    ],
  };
  await page.route('**/variant-photos/**', route => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="blue"/></svg>',
  }));
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/me') return route.fulfill({ status: 401, json: { detail: 'Sign in' } });
    if (path === '/api/products/991') return route.fulfill({ json: product });
    if (path === '/api/products') return route.fulfill({ json: { results: [], count: 0 } });
    return route.fulfill({ json: [] });
  });
  await page.goto('/products/991');
  const photo = page.locator('.gallery-main img');
  await expect(photo).toHaveAttribute('src', cover);
  await page.getByRole('button', { name: /^Blue \(/ }).click();
  await expect(photo).toHaveAttribute('src', blue);
  await expect(page.getByRole('button', { name: 'View photo 2', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Previous product photo' }).click();
  await expect(photo).toHaveAttribute('src', cover);
  await page.getByRole('button', { name: /^Blue \/ Large/ }).click();
  await expect(photo).toHaveAttribute('src', blue);
  await page.getByRole('button', { name: 'View photo 1', exact: true }).click();
  await expect(photo).toHaveAttribute('src', cover);
  await page.getByRole('button', { name: /^Blue \(/ }).click();
  await expect(photo).toHaveAttribute('src', blue);
  await page.getByRole('button', { name: /^No mapped photo/ }).click();
  await expect(photo).toHaveAttribute('src', cover);
});

test('product detail flash timer stays compact beside sale price details', async ({ page }) => {
  const product = {
    id: 992,
    title: 'Flash deal product',
    description: 'A product with a limited-time offer.',
    category: 'electronics',
    brand: 'Demo',
    price: '100.00',
    sale_price: '80.00',
    discount: 20,
    available: 5,
    store: 1,
    store_name: 'Demo',
    store_username: 'demo',
    average_rating: '0',
    rating_count: 0,
    sales: 0,
    images: [],
    image: '',
    tags: [],
    created: '2026-10-05T00:00:00Z',
    is_own_store: false,
    is_digital: false,
    flash_sale_end: '2099-12-31T23:59:00Z',
  };
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/me') return route.fulfill({ status: 401, json: { detail: 'Sign in' } });
    if (path === '/api/products/992') return route.fulfill({ json: product });
    if (path === '/api/products') return route.fulfill({ json: { results: [], count: 0 } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/products/992');
  const timer = page.getByLabel(/Flash deal ends in/);
  await expect(timer).toBeVisible();
  const timerBox = await timer.boundingBox();
  const priceBox = await page.locator('.detail-price').boundingBox();
  expect(timerBox).not.toBeNull();
  expect(priceBox).not.toBeNull();
  expect(timerBox!.width).toBeLessThan(priceBox!.width / 2);
});

test('merchant image mapping survives saving and reopening a variant', async ({ page }) => {
  const cover = 'http://127.0.0.1:3000/variant-photos/black.svg';
  const blue = 'http://127.0.0.1:3000/variant-photos/blue.svg';
  let product = {
    id: 991, title: 'Mapped shirt', description: 'A shirt with color options.', category: 'outwear',
    brand: 'Demo', price: '100.00', discount: 0, available: 20, visibility: true,
    weight: '1.00', is_digital: false, digital_file_url: '', image_url: cover,
    images: [{ id: 1, image: cover }, { id: 2, image: blue }], tags: [], sales: 0,
    variants: [{ name: 'Blue', price_delta: '23.00', available: 10, sku: 'SHIRT-BLUE', image_url: '' }],
  };
  await page.route('**/variant-photos/**', route => route.fulfill({ contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="blue"/></svg>' }));
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/me') return route.fulfill({ json: { id: 7, first_name: 'Demo', last_name: 'Seller', email: 'seller@proace.local' } });
    if (path === '/api/stores') return route.fulfill({ json: { count: 1, results: [{ id: 1, name: 'Demo', status: 'active' }] } });
    if (path === '/api/stores/1/products/991') {
      if (route.request().method() === 'PATCH') product = { ...product, ...route.request().postDataJSON() };
      return route.fulfill({ json: product });
    }
    if (path === '/api/cart') return route.fulfill({ json: { items: [], subtotal: '0', shipping: '0', total: '0' } });
    if (path.endsWith('/specifications')) return route.fulfill({ json: {} });
    return route.fulfill({ json: [] });
  });
  await page.goto('/merchant/products/991');
  await page.getByRole('combobox', { name: 'Variant image', exact: true }).selectOption(blue);
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect.poll(() => product.variants[0].image_url).toBe(blue);
  expect(product.variants[0].sku).toBe('SHIRT-BLUE');
  expect(product.variants[0].price_delta).toBe('23.00');
  await page.reload();
  await expect(page.getByRole('combobox', { name: 'Variant image', exact: true })).toHaveValue(blue);
});
