import { expect, test, type Page, type Route } from '@playwright/test';
import type { Product } from '../src/lib/types';

function savedProduct(id: number): Product {
  return {
    id, title: `Saved book ${id}`, description: 'A saved product', category: 'books',
    brand: 'Test', price: '10.00', sale_price: '10.00', discount: 0, available: 5,
    average_rating: '0', rating_count: 0, store: 1, store_name: 'Test store',
    store_username: 'test-store', image: '', images: [], tags: [],
    created: '2026-10-19T00:00:00Z', is_digital: false, is_own_store: false,
  };
}

async function prepare(page: Page, signedIn: boolean): Promise<void> {
  await page.route('**/api/**', async (route: Route): Promise<void> => {
    const path: string = new URL(route.request().url()).pathname;
    if (path === '/api/me') {
      await route.fulfill({ status: signedIn ? 200 : 401, json: signedIn ? {
        id: 100, first_name: 'Buyer', email: 'buyer@test.local',
        is_staff: false, is_superuser: false, is_business_admin: false,
      } : { detail: 'Sign in required' } });
      return;
    }
    if (path === '/api/cart') {
      await route.fulfill({ json: { items: [], subtotal: '0', shipping: '0', total: '0' } });
      return;
    }
    await route.fulfill({ json: [] });
  });
}

test('removing the only item on page two returns to available saved items', async ({ page }) => {
  await prepare(page, false);
  const products: Product[] = Array.from({ length: 21 }, (_, index: number) => savedProduct(index + 1));
  await page.addInitScript((items: Product[]) => {
    localStorage.setItem('proace-saved', JSON.stringify(items));
  }, products);
  await page.goto('/saved', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.product-card')).toHaveCount(20);
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.locator('.product-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Unsave Saved book 21', exact: true }).click();
  await expect(page.locator('.product-card')).toHaveCount(20);
});

test('a failed wishlist request is visible and can be retried', async ({ page }) => {
  await prepare(page, true);
  let attempts: number = 0;
  await page.route('**/api/wishlist', async (route: Route): Promise<void> => {
    attempts += 1;
    await route.fulfill(attempts === 1
      ? { status: 400, json: { detail: 'Saved items could not load.' } }
      : { json: [savedProduct(1)] });
  });
  await page.goto('/saved', { waitUntil: 'domcontentloaded' });
  await expect(page.getByText('Saved items could not load.')).toBeVisible();
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Saved book 1', exact: true })).toBeVisible();
  expect(attempts).toBe(2);
});

test('legacy guest saved products remain in the standard listing filter', async ({ page }) => {
  await prepare(page, false);
  await page.addInitScript((item: Product) => {
    localStorage.setItem('proace-saved', JSON.stringify([item]));
  }, savedProduct(1));
  await page.goto('/saved', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.product-card')).toHaveCount(1);
  await page.getByRole('combobox', { name: 'saved products: Listing type', exact: true }).selectOption('standard');
  await expect(page.locator('.product-card')).toHaveCount(1);
});
