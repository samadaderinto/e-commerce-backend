import { expect, test } from '@playwright/test';

test('owned listings cannot be bought from catalog or product page', async ({ page }) => {
  const product = {
    id: 901, title: 'Merchant test speaker', description: 'Portable speaker',
    category: 'electronics', brand: 'Test', price: '10000', sale_price: '10000',
    discount: 0, available: 5, average_rating: 0, rating_count: 0,
    store: 42, store_name: 'My second store', store_username: 'second-store',
    image: '', images: [], tags: [], is_own_store: true,
  };
  let cartMutations = 0;
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let json: unknown = {};
    if (path === '/api/me') json = { id: 7, email: 'seller@test.com', first_name: 'Seller' };
    else if (path === '/api/products/901') json = product;
    else if (path === '/api/products') json = { count: 1, page: 1, pages: 1, results: [product] };
    else if (path === '/api/cart') {
      if (route.request().method() !== 'GET') cartMutations++;
      json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    } else json = [];
    await route.fulfill({ json });
  });
  await page.goto('/shop');
  await expect(page.locator('.quick-add').getByText('Your listing')).toBeDisabled();
  await page.goto('/products/901');
  await expect(page.locator('.purchase-actions').getByRole('button', { name: 'Your listing' })).toBeDisabled();
  expect(cartMutations).toBe(0);
});
