import { expect, test } from '@playwright/test';

test('storefront excludes unrelated feature code and navigates between split routes', async ({ page }) => {
  const scripts: Promise<string>[] = [];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.request().resourceType() === 'script' && response.url().includes('/_next/')) {
      scripts.push(response.text());
    }
  });
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/me') {
      return route.fulfill({ status: 401, json: { detail: 'Sign in required' } });
    }
    if (path.includes('firebase')) {
      return route.fulfill({ json: { available: false } });
    }
    return route.fulfill({ json: { count: 0, results: [], pages: 1 } });
  });

  await page.goto('/');
  await expect(page.locator('main h1')).toBeVisible();
  await page.locator('a[href="/shop"]').first().click();
  await expect(page).toHaveURL(/\/shop$/);
  await expect(page.locator('main h1')).toBeVisible();
  await page.locator('a[href="/cart"]').first().click();
  await expect(page).toHaveURL(/\/cart$/);
  await expect(page.getByRole('heading', { name: 'Room for something good' })).toBeVisible();

  const source = (await Promise.all(scripts)).join('\n');
  expect(source).not.toContain('Merchant Payout Approvals');
  expect(source).not.toContain('Request store payout');
  expect(source).not.toContain('failed-service-worker-registration');
  expect(errors).toEqual([]);
});
