import { expect, test, type Route } from '@playwright/test';
import type { Product, Review } from '../src/lib/types';

const product: Product = {
  id: 9903, title: 'Review total regression', description: 'A catalog product.',
  category: 'books', brand: 'Test', price: '20.00', sale_price: '20.00',
  discount: 0, available: 5, average_rating: '5.00', rating_count: 75,
  store: 1, store_name: 'Test store', store_username: 'test-store',
  image: '', images: [], tags: [], created: '2026-10-19T00:00:00Z',
  is_own_store: false, is_digital: false,
};
const review: Review = {
  id: 1, author: 'Buyer', rating: 5, label: 'Useful book', comment: 'A useful read.',
  created: '2026-10-19T00:00:00Z', is_verified_buyer: true,
};

test('review pagination keeps an older own review editable', async ({ page }) => {
  const own: Review = { ...review, id: 51, label: 'My original title', is_own_review: true };
  await page.route('**/api/**', async (route: Route): Promise<void> => {
    const url: URL = new URL(route.request().url());
    let json: unknown = [];
    if (url.pathname === '/api/me') json = { id: 9, email: 'buyer@test.local', first_name: 'Buyer' };
    if (url.pathname === '/api/products/9903') json = product;
    if (url.pathname === '/api/products') json = { count: 0, results: [] };
    if (url.pathname === '/api/products/9903/reviews') {
      json = { count: 51, results: url.searchParams.get('offset') === '20' ? [own] : [review], own_review: own };
    }
    if (url.pathname === '/api/cart') json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    await route.fulfill({ json });
  });
  await page.goto('/products/9903', { waitUntil: 'domcontentloaded' });
  await page.getByRole('tab', { name: /^Reviews/ }).click();
  await expect(page.getByRole('heading', { name: 'Edit your review', exact: true })).toBeVisible();
  await expect(page.getByLabel('Review title')).toHaveValue(own.label);
  await expect(page.getByRole('button', { name: 'Delete your review', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.getByRole('heading', {
    name: `${own.label} (Your Review · Editable below)`, exact: true,
  })).toBeVisible();
});

test('related products can recover independently from an error', async ({ page }) => {
  let attempts: number = 0;
  await page.route('**/api/**', async (route: Route): Promise<void> => {
    const path: string = new URL(route.request().url()).pathname;
    if (path === '/api/me') {
      await route.fulfill({ status: 401, json: { detail: 'Sign in required' } });
      return;
    }
    if (path === '/api/products' && ++attempts === 1) {
      await route.fulfill({ status: 400, json: { detail: 'Related products could not load.' } });
      return;
    }
    let json: unknown = { count: 0, results: [], pages: 1 };
    if (path === '/api/products/9903') json = product;
    if (path === '/api/products/9903/reviews') json = [];
    await route.fulfill({ json });
  });
  await page.goto('/products/9903', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: product.title })).toBeVisible();
  await expect(page.getByText('Related products could not load.')).toBeVisible();
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No related finds right now' })).toBeVisible();
  expect(attempts).toBe(2);
});

for (const theme of ['light', 'dark']) {
  test(`product totals do not shrink to the loaded review list in ${theme} mode`, async ({ page }) => {
    await page.route('**/api/**', async (route: Route): Promise<void> => {
      const path: string = new URL(route.request().url()).pathname;
      if (path === '/api/me') {
        await route.fulfill({ status: 401, json: { detail: 'Sign in required' } });
        return;
      }
      let json: unknown = { count: 0, results: [], pages: 1 };
      if (path === '/api/products/9903') json = product;
      if (path === '/api/products/9903/reviews') json = [review];
      await route.fulfill({ json });
    });
    await page.goto('/products/9903', { waitUntil: 'domcontentloaded' });
    await page.evaluate((value: string) => document.documentElement.setAttribute('data-theme', value), theme);
    await expect(page.getByRole('heading', { name: product.title })).toBeVisible();
    await page.getByRole('tab', { name: /^Reviews/ }).click();
    await expect(page.getByText(review.label, { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '75 reviews', exact: true })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Reviews (75)', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'No related finds right now' })).toBeVisible();
  });
}
