import { expect, test, type Route } from '@playwright/test';
import type { Cart, Product, ShippingRate } from '../src/lib/types';

const product: Product = {
  id: 9906, title: 'Digital checkout audit', description: 'Test download', category: 'books',
  brand: 'Test', price: '20.00', sale_price: '20.00', discount: 0, available: 100,
  average_rating: '0', rating_count: 0, store: 1, store_name: 'Test store',
  store_username: 'test-store', image: '', images: [], tags: [],
  created: '2026-10-19T00:00:00Z', is_digital: true, is_own_store: false,
};
const cart: Cart = {
  items: [{ product, quantity: 1, total: '20.00', purchasable: true }],
  subtotal: '20.00', shipping: '0.00', total: '20.00',
};
const rate: ShippingRate = {
  carrier: 'digital', currency: 'USD', source: 'test', quote_token: 'test-only-token',
  service_id: 'digital_delivery', name: 'Digital delivery', description: 'Download',
  amount: '0.00', tax: '0.00', is_default: true,
};

test('checkout waits for pending coupon validation before permitting payment', async ({ page }) => {
  let release: () => void = () => {};
  const pending: Promise<void> = new Promise(resolve => { release = resolve; });
  await page.route('**/api/**', async (route: Route): Promise<void> => {
    const path: string = new URL(route.request().url()).pathname;
    if (path === '/api/me') {
      await route.fulfill({ json: {
        id: 100, first_name: 'Buyer', email: 'buyer@test.local',
        is_staff: false, is_superuser: false, is_business_admin: false,
      } });
      return;
    }
    if (path === '/api/checkout/validate-coupon') {
      await pending;
      await route.fulfill({ json: { code: 'SAVE', discount_amount: '2.00', message: 'Coupon applied' } });
      return;
    }
    let json: unknown = [];
    if (path === '/api/cart') json = cart;
    if (path === '/api/wallet') json = { balance: '100.00', transactions: [] };
    if (path === '/api/checkout/shipping-rates') json = [rate];
    await route.fulfill({ json });
  });
  try {
    await page.goto('/checkout', { waitUntil: 'domcontentloaded' });
    const pay = page.getByRole('button', { name: /^Pay .* with Stripe$/ });
    await expect(pay).toBeEnabled();
    await page.getByPlaceholder('Enter coupon code').fill('SAVE');
    await page.getByRole('button', { name: 'Apply', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Checking…', exact: true })).toBeVisible();
    await expect(page.getByPlaceholder('Enter coupon code')).toBeDisabled();
    await expect(pay).toBeDisabled();
    release();
    await expect(page.getByText('✓ Coupon applied', { exact: true })).toBeVisible();
    await expect(pay).toBeEnabled();
  } finally {
    release();
  }
});
