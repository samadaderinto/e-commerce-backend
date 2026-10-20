import { expect, test, type Page, type Route } from '@playwright/test';
import type { Product } from '../src/lib/types';

const deal: Product = {
  id: 9001, title: 'A deal beyond the bestseller page', description: 'Test item',
  category: 'books', brand: 'Test', price: '20.00', sale_price: '10.00',
  discount: 50, available: 5, average_rating: '0', rating_count: 0,
  store: 1, store_name: 'Test store', store_username: 'test-store',
  image: '', images: [], tags: [], created: '2026-10-19T00:00:00Z',
  is_own_store: false, is_digital: false,
};

async function prepare(page: Page): Promise<void> {
  await page.route('**/api/**', async (route: Route): Promise<void> => {
    const path: string = new URL(route.request().url()).pathname;
    if (path === '/api/me') {
      await route.fulfill({ status: 401, json: { detail: 'Sign in required' } });
      return;
    }
    await route.fulfill({ json: { count: 0, results: [], pages: 1 } });
  });
}

for (const theme of ['light', 'dark']) {
  test(`homepage loads deals independently in ${theme} mode`, async ({ page }) => {
    await prepare(page);
    await page.route('**/api/products?**', async (route: Route): Promise<void> => {
      const params: URLSearchParams = new URL(route.request().url()).searchParams;
      const results: Product[] = params.get('deals') === 'true' ? [deal] : [];
      await route.fulfill({ json: { count: results.length, results, pages: 1 } });
    });
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'Your next favourites', exact: true })).toBeVisible({ timeout: 30000 });
    await page.evaluate((value: string) => document.documentElement.setAttribute('data-theme', value), theme);
    await expect(page.getByRole('link', { name: deal.title, exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'New finds are on their way' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'See all deals' })).toHaveAttribute('href', '/shop?deals=true');
  });
}

test('deals errors are visible and independently retryable', async ({ page }) => {
  await prepare(page);
  let attempts: number = 0;
  await page.route('**/api/products?**', async (route: Route): Promise<void> => {
    const isDeal: boolean = new URL(route.request().url()).searchParams.get('deals') === 'true';
    if (isDeal && ++attempts === 1) {
      await route.fulfill({ status: 400, json: { detail: 'Unable to load offers.' } });
      return;
    }
    await route.fulfill({ json: { count: 0, results: [], pages: 1 } });
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Your next favourites', exact: true })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText('Unable to load offers.')).toBeVisible();
  await page.getByRole('button', { name: /try again/i }).click();
  await expect(page.getByRole('heading', { name: 'No deals right now' })).toBeVisible();
  expect(attempts).toBe(2);
});
