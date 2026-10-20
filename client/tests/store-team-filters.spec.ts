import { expect, test } from '@playwright/test';

for (const theme of ['light', 'dark'] as const) {
  test(`team directory filters and resets in ${theme} mode`, async ({ page }) => {
    const requests: URL[] = [];
    const store = { id: 42, name: 'Fixture store', user_role: 'owner', status: 'active' };
    await page.addInitScript((value: string): void => {
      localStorage.setItem('proace-theme', value);
    }, theme);
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace(/\/$/, '');
      let json: unknown = {};
      if (path === '/api/me') {
        json = { id: 7, first_name: 'Owner', email: 'owner@example.test' };
      } else if (path === '/api/stores') {
        json = { count: 1, results: [store] };
      } else if (path === '/api/stores/42') {
        json = store;
      } else if (path === '/api/cart') {
        json = { items: [], subtotal: '0', shipping: '0', total: '0' };
      } else if (path === '/api/wishlist') {
        json = [];
      } else if (path === '/api/stores/42/team') {
        requests.push(url);
        const hidden = Boolean(url.searchParams.get('search'));
        json = {
          count: hidden ? 0 : 1,
          results: hidden ? [] : [{
            id: 3,
            user_id: 8,
            email: 'catalog@example.test',
            first_name: 'Catalog',
            role: 'catalog_manager',
            role_display: 'Catalog manager',
            created: '2026-10-01T12:00:00Z',
            updated: '2026-10-01T12:00:00Z',
          }],
        };
      } else if (path.includes('notifications')) {
        json = { count: 0, results: [], unread: 0, total: 0 };
      }
      await route.fulfill({ json });
    });
    await page.goto('/merchant/team?store=42');
    await expect(page.getByText('catalog@example.test', { exact: true })).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await page.getByLabel('team members: Role', { exact: true }).selectOption('catalog_manager');
    await page.getByLabel('Search team members', { exact: true }).fill('missing-person');
    await expect(page.getByText('No team members match these filters. Reset filters to see everyone.')).toBeVisible();
    expect(requests.at(-1)?.searchParams.get('role')).toBe('catalog_manager');
    expect(requests.at(-1)?.searchParams.get('paginated')).toBe('1');
    await page.getByRole('button', { name: 'Reset filters', exact: true }).click();
    await expect(page.getByText('catalog@example.test', { exact: true })).toBeVisible();
    await expect(page.getByLabel('team members: Role', { exact: true })).toHaveValue('');
  });
}
