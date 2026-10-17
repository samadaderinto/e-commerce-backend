import { expect, test } from '@playwright/test';

test('app settings explain browser alerts and link guests to sign in', async ({ page }) => {
  await page.route('**/api/**', route => route.fulfill({
    status: 401,
    json: { detail: 'Authentication required' },
  }));

  await page.goto('/settings');
  await page.getByText('Push notifications on this device', { exact: true }).click();

  await expect(page.getByRole('region', { name: 'Browser alert settings' })).toContainText(
    'Sign in to connect this browser to your account’s notifications.',
  );
  await expect(page.getByRole('link', { name: 'Sign in to enable alerts' })).toHaveAttribute(
    'href',
    '/login?next=/settings',
  );
});

test('theme toggles persist through refresh and synchronize existing and new tabs', async ({ page, context }) => {
  await context.route('**/api/**', route => route.fulfill({ status: 401, json: { detail: 'Authentication required' } }));
  await page.goto('/settings');
  await page.getByRole('radio', { name: /^Light/ }).check();
  const second = await context.newPage();
  await second.goto('/settings');
  await page.getByRole('button', { name: 'Switch to dark mode' }).click();
  for (const tab of [page, second]) {
    await expect(tab.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(tab.getByRole('radio', { name: /^Dark/ })).toBeChecked();
  }
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  const third = await context.newPage();
  await third.goto('/settings');
  await expect(third.locator('html')).toHaveAttribute('data-theme', 'dark');
  await second.getByRole('button', { name: 'Switch to light mode' }).click();
  for (const tab of [page, second, third]) {
    await expect(tab.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(tab.getByRole('radio', { name: /^Light/ })).toBeChecked();
  }
  await second.reload();
  await expect(second.locator('html')).toHaveAttribute('data-theme', 'light');
  await third.getByRole('radio', { name: /^System/ }).check();
  for (const tab of [page, second, third]) {
    await expect(tab.getByRole('radio', { name: /^System/ })).toBeChecked();
  }
});
