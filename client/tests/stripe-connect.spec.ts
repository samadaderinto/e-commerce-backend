import { expect, test } from '@playwright/test';

test('Stripe return shows connected state and removes the onboarding button', async ({ page }) => {
  let onboardingRequests = 0;
  let statusRequests = 0;
  const observedPaths: string[] = [];
  await page.route('**/api/**', async (route): Promise<void> => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    observedPaths.push(path);
    let body: unknown = {};
    if (path === '/api/me') {
      body = { id: 7, first_name: 'Seller', email: 'seller@test.com' };
    } else if (path === '/api/stores') {
      body = { count: 1, results: [{ id: 1, name: 'Apex Athletics', username: 'apex', status: 'active' }] };
    } else if (path.endsWith('/stores/1/stripe-status')) {
      statusRequests += 1;
      body = {
        connected: true,
        details_submitted: true,
        payouts_enabled: true,
        currently_due: [],
      };
    } else if (path.endsWith('/stores/1/profile')) {
      body = { email: 'seller@test.com', bio: '' };
    } else if (path.endsWith('/stores/1/pickup-address')) {
      body = { address: '1 Main St', city: 'Tampa', state: 'FL', country: 'US', zip: '33602' };
    } else if (path.endsWith('/stores/1/connect-stripe')) {
      onboardingRequests += 1;
      body = { connected: true, url: '', stripe_account_id: 'acct_real_connected' };
    } else if (path === '/api/cart') {
      body = { items: [], subtotal: '0', shipping: '0', total: '0' };
    } else if (path === '/api/wishlist') {
      body = [];
    }
    await route.fulfill({ json: body });
  });

  await page.goto('/merchant/settings?stripe_onboarding=return', { waitUntil: 'domcontentloaded' });
  await expect.poll(() => statusRequests, { message: observedPaths.join(', ') }).toBeGreaterThan(0);
  await expect(page.getByRole('status').filter({ hasText: 'Stripe payouts connected' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Connect Stripe payouts' })).toHaveCount(0);
  await expect(page).toHaveURL(/\/merchant\/settings$/);
  expect(onboardingRequests).toBe(0);
});
