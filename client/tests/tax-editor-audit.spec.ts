import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const admin = {
  id: 71, first_name: 'Audit', last_name: 'Admin', email: 'audit@test.local',
  is_staff: true, is_superuser: false, is_business_admin: true,
  must_change_password: false,
};

async function mockBase(page: Page): Promise<void> {
  await page.route('**/api/**', async route => {
    const path: string = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ json: admin });
    if (path.includes('notifications')) {
      return route.fulfill({ json: { unread: 0, total: 0, results: [] } });
    }
    return route.fulfill({ json: { count: 0, results: [] } });
  });
}

for (const [rate, percentage] of [
  ['0.00000', '0'], ['0.00001', '0.001'], ['0.00500', '0.5'],
  ['0.01000', '1'], ['0.08875', '8.875'], ['1.00000', '100'],
] as const) {
  test(`tax editor preserves ${rate} when saving an unchanged rule`, async ({ page }) => {
    await mockBase(page);
    let submittedRate: unknown;
    await page.route('**/api/admin/taxes**', async route => {
      if (route.request().method() === 'PATCH') {
        const payload: { rate: string } = route.request().postDataJSON();
        submittedRate = payload.rate;
        return route.fulfill({ json: { id: 1, ...payload } });
      }
      return route.fulfill({ json: {
        provider: 'local', stripe_tax_enabled: false, default_tax_rate: '0',
        summary: { total_jurisdictions: 1, active_jurisdictions: 1, zip_overrides: 1 },
        results: [{
          id: 1, country: 'US', state: 'CA', postal_code: '902', name: 'Audit rule',
          rate, tax_shipping: false, tax_digital: true, is_active: true,
        }],
      } });
    });
    await page.goto('/admin/taxes');
    await page.getByRole('button', { name: 'Edit', exact: true }).click();
    await expect(page.getByLabel('Tax Rate (Percentage, e.g. 0.5 for 0.5%)')).toHaveValue(percentage);
    await page.getByRole('button', { name: 'Save Changes' }).click();
    await expect.poll(() => submittedRate).toBe(rate);
  });
}

test('tax creation submits a percentage below one and rejects malformed values', async ({ page }) => {
  await mockBase(page);
  const payloads: Array<{ rate: string }> = [];
  await page.route('**/api/admin/taxes**', async route => {
    if (route.request().method() === 'POST') {
      const payload: { rate: string } = route.request().postDataJSON();
      payloads.push(payload);
      return route.fulfill({ status: 201, json: { id: 1, ...payload } });
    }
    return route.fulfill({ json: {
      provider: 'local', stripe_tax_enabled: false, default_tax_rate: '0',
      summary: { total_jurisdictions: 0, active_jurisdictions: 0, zip_overrides: 0 },
      results: [],
    } });
  });
  await page.goto('/admin/taxes');
  await page.getByRole('button', { name: /Add.*Jurisdiction|Add.*Rule/i }).click();
  await page.getByLabel('State / Territory Code (2 Letters)').fill('CA');
  await page.getByLabel('Jurisdiction Label / Name').fill('Low rate');
  const rate = page.getByLabel('Tax Rate (Percentage, e.g. 0.5 for 0.5%)');
  for (const invalid of ['0.5invalid', '101', '-1', 'Infinity']) {
    await rate.fill(invalid);
    await page.getByRole('button', { name: 'Create Jurisdiction' }).click();
    await expect(page.getByText('Please enter a tax percentage between 0 and 100.').last()).toBeVisible();
    expect(payloads).toHaveLength(0);
  }
  await rate.fill('0.5');
  await page.getByRole('button', { name: 'Create Jurisdiction' }).click();
  await expect.poll(() => payloads[0]?.rate).toBe('0.00500');
});

test('admin order options only offer cancellation for unshipped physical orders', async ({ page }) => {
  await mockBase(page);
  await page.route('**/api/admin/staff/orders**', route => route.fulfill({ json: {
    count: 4,
    results: [
      { id: 1, orderId: 'DIGITAL-PENDING', status: 'pending', items_snapshot: [{ is_digital: true }] },
      { id: 2, orderId: 'DIGITAL-CONFIRMED', status: 'confirmed', items_snapshot: [{ is_digital: true }] },
      { id: 3, orderId: 'PHYSICAL-SHIPPED', status: 'shipped', items_snapshot: [{ is_digital: false }] },
      { id: 4, orderId: 'PHYSICAL-CONFIRMED', status: 'confirmed', items_snapshot: [{ is_digital: false }] },
    ].map(order => ({ ...order, total: '10.00', buyer_email: 'buyer@test.local', created: '2026-10-01T00:00:00Z' })),
  } }));
  await page.goto('/admin/orders');
  for (const reference of ['DIGITAL-PENDING', 'DIGITAL-CONFIRMED', 'PHYSICAL-SHIPPED']) {
    const options = page.getByLabel(`Override status for order ${reference}`).locator('option');
    await expect(options.filter({ hasText: /^cancelled$/ })).toHaveCount(0);
  }
  await expect(page.getByLabel('Override status for order PHYSICAL-CONFIRMED').locator('option[value="cancelled"]')).toHaveCount(1);
});
