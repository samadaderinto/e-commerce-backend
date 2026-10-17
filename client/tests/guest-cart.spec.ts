import { expect, test } from '@playwright/test';

for (const theme of ['light', 'dark']) {
  for (const kind of ['physical', 'digital', 'mixed']) {
    test(`guest ${kind} cart uses accurate totals in ${theme} mode`, async ({ page }) => {
      await page.route('**/api/**', route => route.fulfill({
        status: 401,
        json: { detail: 'Sign in required' },
      }));
      await page.addInitScript(({ selectedTheme, selectedKind }) => {
        localStorage.setItem('proace-theme', selectedTheme);
        const product = {
          id: 1,
          title: 'Guest cart fixture',
          price: '25.00',
          sale_price: '25.00',
          available: 5,
          is_digital: selectedKind === 'digital',
        };
        const rows = [{ product, quantity: 1, total: '25.00', purchasable: true }];
        if (selectedKind === 'mixed') {
          rows.push({ ...rows[0], product: { ...product, id: 2, is_digital: true } });
        }
        localStorage.setItem('proace-cart', JSON.stringify(rows));
      }, { selectedTheme: theme, selectedKind: kind });

      await page.goto('/cart');
      const summary = page.locator('.order-summary');
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
      await expect(summary.locator('.summary-total')).toContainText(kind === 'mixed' ? '$50.00' : '$25.00');
      await expect(summary).toContainText(kind === 'digital' ? 'Free' : 'Calculated at checkout');
      await expect(summary).not.toContainText('$2,500');
      await page.reload();
      await expect(summary.locator('.summary-total')).toContainText(kind === 'mixed' ? '$50.00' : '$25.00');
    });
  }
}
