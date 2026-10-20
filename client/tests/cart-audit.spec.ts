import { expect, test, type Route } from '@playwright/test';

for (const theme of ['light', 'dark']) {
  test(`failed cart loading can recover in ${theme} mode`, async ({ page }) => {
    let attempts: number = 0;
    await page.route('**/api/**', async (route: Route): Promise<void> => {
      const path: string = new URL(route.request().url()).pathname;
      if (path === '/api/me') {
        await route.fulfill({ json: {
          id: 100, first_name: 'Buyer', email: 'buyer@test.local',
          is_staff: false, is_superuser: false, is_business_admin: false,
        } });
        return;
      }
      if (path === '/api/cart') {
        attempts += 1;
        await route.fulfill(attempts === 1
          ? { status: 400, json: { detail: 'Your bag could not load.' } }
          : { json: { items: [], subtotal: '0', shipping: '0', total: '0' } });
        return;
      }
      await route.fulfill({ json: [] });
    });
    await page.goto('/cart', { waitUntil: 'domcontentloaded' });
    await page.evaluate((value: string) => document.documentElement.setAttribute('data-theme', value), theme);
    await expect(page.getByText('Your bag could not load.')).toBeVisible();
    await page.getByRole('button', { name: 'Try again', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Room for something good' })).toBeVisible();
    expect(attempts).toBe(2);
  });
}
