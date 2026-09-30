import { test, expect, Page } from '@playwright/test';

const password = process.env.E2E_DEMO_PASSWORD || 'ProaceDemo2026!';

async function login(page: Page, role = 'shopper', next = '/account') {
  await page.goto(`/login?next=${next}`);
  await page.getByLabel('Email address').fill(`${role}@proace.local`);
  await page.getByLabel('Password', {exact: true}).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(next));
}

async function noOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  expect(overflow).toBe(false);
}

test('storefront, assets, search and saved items', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', {name: 'Everyday essentials.'})).toBeVisible();
  await expect(page.locator('.product-card')).toHaveCount(12);
  await page.locator('.hero-image').evaluate((image: HTMLImageElement) => image.decode());
  await expect.poll(() => page.locator('.product-photo img').evaluateAll(images => images.filter(image => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0).length), {timeout: 30000}).toBeGreaterThan(0);
  await page.locator('img').evaluateAll(images => { for (const image of images) (image as HTMLImageElement).loading = 'eager'; });
  await page.locator('.product-photo img').evaluateAll(async images => { await Promise.all(images.map(image => (image as HTMLImageElement).decode().catch(() => null))); });
  await noOverflow(page);
  await page.screenshot({path: `../artifacts/home-${testInfo.project.name}.png`});
  await page.goto('/shop?search=headphones');
  await expect(page.locator('.product-card')).toHaveCount(2);
  await page.locator('.save-button').first().click();
  await page.goto('/saved');
  await expect(page.locator('.product-card')).toHaveCount(1);
  await noOverflow(page);
  expect(errors).toEqual([]);
});

test('guest bag merges on sign-in and checkout creates an order', async ({ page }, testInfo) => {
  await page.goto('/products/2');
  await expect(page.getByRole('heading', {name: 'Everyday canvas backpack'})).toBeVisible();
  await page.locator('.purchase-actions').getByRole('button', {name: 'Add to bag', exact: true}).click();
  await page.goto('/cart');
  await expect(page.locator('.cart-row')).toHaveCount(1);
  await noOverflow(page);
  await page.getByRole('link', {name: 'Continue to checkout'}).click();
  await page.locator('main').getByRole('link', {name: 'Sign in', exact: true}).click();
  await page.getByLabel('Email address').fill('shopper@proace.local');
  await page.getByLabel('Password', {exact: true}).fill(password);
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page).toHaveURL(/\/checkout/);
  await expect(page.getByRole('button', {name: 'Place order'})).toBeEnabled();
  await page.screenshot({path: `../artifacts/checkout-${testInfo.project.name}.png`, fullPage: true});
  await page.getByRole('button', {name: 'Place order'}).click();
  await expect(page).toHaveURL(/\/orders\/\d+\?placed=true/);
  await expect(page.getByRole('heading', {name: 'It’s on the list.'})).toBeVisible();
  await expect(page.getByText('Cash on delivery', {exact: true})).toBeVisible();
  await noOverflow(page);
  const cookies = await page.context().cookies();
  expect(cookies.find(cookie => cookie.name === 'proace_access')?.httpOnly).toBe(true);
  await page.goto('/account/orders');
  await expect(page.locator('.order-row').first()).toBeVisible();
});

test('merchant dashboard and real product onboarding', async ({ page }, testInfo) => {
  await login(page, 'seller', '/merchant');
  await expect(page.getByRole('heading', {name: 'Hello, Jordan.'})).toBeVisible();
  await expect(page.locator('.stat-item')).toHaveCount(4);
  await noOverflow(page);
  await page.screenshot({path: `../artifacts/merchant-${testInfo.project.name}.png`, fullPage: true});
  await page.getByRole('link', {name: 'Add product', exact: true}).click();
  const title = `Test desk accessory ${testInfo.project.name} ${Date.now()}`;
  await page.getByLabel('Product title').fill(title);
  await page.getByLabel('Description', {exact: true}).fill('Created by the end-to-end merchant workflow test.');
  await page.getByRole('combobox', {name: 'Category', exact: true}).selectOption('electronics');
  await page.getByLabel('Price (NGN)').fill('9500');
  await page.getByLabel('Stock quantity').fill('8');
  await page.getByRole('button', {name: 'Create product'}).click();
  await expect(page).toHaveURL(/\/merchant\/products\/\d+/);
  await expect(page.getByLabel('Product title')).toHaveValue(title);
  await page.getByLabel('Publish to the marketplace').check();
  await page.getByRole('button', {name: 'Save changes'}).click();
  await expect(page.getByRole('link', {name: 'View listing'})).toBeVisible();
  await page.getByLabel('Publish to the marketplace').uncheck();
  await page.getByRole('button', {name: 'Save changes'}).click();
  await expect(page.getByRole('link', {name: 'View listing'})).toHaveCount(0);
  await noOverflow(page);
});

test('forms validate and unknown routes return a real 404', async ({ page }) => {
  await page.goto('/register');
  await page.getByRole('button', {name: 'Create account', exact: true}).click();
  expect(await page.locator('input:invalid').count()).toBeGreaterThan(0);
  await noOverflow(page);
  const response = await page.goto('/not-a-real-page');
  expect(response?.status()).toBe(404);
  await expect(page.getByRole('heading', {name: 'This find got away.'})).toBeVisible();
});
