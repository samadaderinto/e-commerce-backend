import { expect, test, type Route } from '@playwright/test';

for (const theme of ['light', 'dark']) {
  test(`wallet failure is not displayed as a zero balance in ${theme} mode`, async ({ page }) => {
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
      if (path === '/api/wallet') {
        attempts += 1;
        await route.fulfill(attempts === 1
          ? { status: 400, json: { detail: 'Wallet information could not load.' } }
          : { json: { balance: '0.00', count: 0, transactions: [] } });
        return;
      }
      if (path === '/api/cart') {
        await route.fulfill({ json: { items: [], subtotal: '0', shipping: '0', total: '0' } });
        return;
      }
      const json: unknown = path === '/api/orders' ? { count: 0, results: [], pages: 1 } : [];
      await route.fulfill({ json });
    });
    await page.goto('/account/wallet', { waitUntil: 'domcontentloaded' });
    await page.evaluate((value: string) => document.documentElement.setAttribute('data-theme', value), theme);
    await expect(page.getByText('Wallet information could not load.')).toBeVisible();
    await expect(page.locator('.wallet-balance-amount')).toHaveText('Unavailable');
    await expect(page.getByRole('button', { name: 'Add funds', exact: true })).toBeDisabled();
    await page.getByRole('button', { name: 'Try again', exact: true }).click();
    await expect(page.locator('.wallet-balance-amount')).toContainText('$0');
    await expect(page.getByRole('button', { name: 'Add funds', exact: true })).toBeEnabled();
    expect(attempts).toBe(2);
  });
}
