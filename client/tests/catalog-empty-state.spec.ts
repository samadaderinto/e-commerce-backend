import { expect, test, type Route } from '@playwright/test';

for (const theme of ['light', 'dark']) {
  test(`empty filtered catalog can reset without leaving its store in ${theme} mode`, async ({ page }) => {
    await page.route('**/api/**', async (route: Route): Promise<void> => {
      const path: string = new URL(route.request().url()).pathname;
      if (path === '/api/me') {
        await route.fulfill({ status: 401, json: { detail: 'Sign in required' } });
        return;
      }
      await route.fulfill({ json: { count: 0, results: [], pages: 1 } });
    });
    await page.goto('/shop?store=42&search=missing&min_price=10', { waitUntil: 'domcontentloaded' });
    await page.evaluate((value: string) => document.documentElement.setAttribute('data-theme', value), theme);
    await expect(page.getByText('No products match your search and filters. Clear them to see available listings.')).toBeVisible();
    await page.getByRole('button', { name: 'Clear search and filters', exact: true }).click();
    await expect(page).toHaveURL(/\/shop\?store=42$/);
    await expect(page.getByText('There are no products available here right now. Please check back soon.')).toBeVisible();
  });
}
