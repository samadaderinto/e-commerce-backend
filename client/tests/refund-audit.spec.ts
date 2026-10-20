import { expect, test, type Route } from '@playwright/test';

for (const theme of ['light', 'dark']) {
  for (const processing of [true, false]) {
    test(`refund ${processing ? 'processing lock' : 'delivery window'} in ${theme} mode`, async ({ page }) => {
      const now: number = Date.now();
      const recent: string = new Date(now - 24 * 60 * 60 * 1000).toISOString();
      const old: string = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();
      await page.route('**/api/**', async (route: Route): Promise<void> => {
        const path: string = new URL(route.request().url()).pathname;
        let json: unknown = [];
        if (path === '/api/me') {
          json = { id: 100, email: 'buyer@test.local', first_name: 'Buyer' };
        } else if (path === '/api/orders/42') {
          json = {
            id: 42, reference: 'REFUND-AUDIT', status: 'delivered',
            created: old, delivered_at: recent, total: '20', subtotal: '20',
            paid_total: '20', refunded_total: '0', payment_type: 'stripe',
            tracking_events: [], address: {}, fulfillments: [
              { store: 1, store_name: 'Fixture store', status: 'delivered', delivered_at: recent },
              { store: 2, store_name: 'Other store', status: 'delivered', delivered_at: old },
            ],
            items: [
              { product: 1, store: 1, title: 'Recently delivered item', quantity: 1, unit_price: '10', is_digital: false },
              { product: 2, store: 2, title: 'Expired item', quantity: 1, unit_price: '10', is_digital: false },
            ],
            active_refund: processing ? {
              id: 1, status: 'pending', is_pending: true, is_editable: false,
              reason: 'Item damaged', refund_type: 'original_payment',
              refund_amount: '10', product_ids: [1], created: recent, updated: recent,
            } : null,
            claimed_product_ids: processing ? [1] : [],
          };
        } else if (path === '/api/cart') {
          json = { items: [], subtotal: '0', shipping: '0', total: '0' };
        }
        await route.fulfill({ json });
      });
      await page.goto('/orders/42', { waitUntil: 'domcontentloaded' });
      await page.evaluate((value: string) => document.documentElement.setAttribute('data-theme', value), theme);
      if (processing) {
        await expect(page.getByText('Your refund is processing with the payment provider and can no longer be edited.')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Edit refund request', exact: true })).toHaveCount(0);
      } else {
        await page.getByRole('button', { name: 'Request a return / refund', exact: true }).click();
        const items = page.locator('.order-refund-item');
        await expect(items.filter({ hasText: 'Recently delivered item' }).getByRole('checkbox')).toBeEnabled();
        await expect(items.filter({ hasText: 'Expired item' }).getByRole('checkbox')).toBeDisabled();
      }
    });
  }
}
