import { expect, test } from '@playwright/test';
import type { VisualSearchDetectedItem, VisualSearchResponse } from '../src/lib/types';

const items: VisualSearchDetectedItem[] = ['Jacket', 'Shoes'].map((label, index) => ({
  id: String(index), label, category: 'outwear', confidence: 0.8,
  box: [0, 0, 1, 1], dominant_colors: [], keywords: [],
}));
const analysis = (index: number): VisualSearchResponse => ({
  method: 'local_clip', message: 'Related catalog items, not verified identical photos.',
  palette: [], detected_items: items, selected_item_id: String(index),
  selected_item: items[index], results: [], query_applied: items[index].label,
});

for (const theme of ['light', 'dark']) {
  test(`uncertain recognition shows an honest empty state in ${theme} mode`, async ({ page }) => {
    await page.route('**/api/products/visual-search/', route => route.fulfill({
      json: {
        method: 'local_clip', message: 'No reliable product subject was recognized. Try text search.',
        palette: [], detected_items: [], selected_item_id: null, selected_item: null,
        results: [], query_applied: '',
      } satisfies VisualSearchResponse,
    }));
    await page.goto('/shop', { waitUntil: 'domcontentloaded' });
    await page.evaluate((value: string) => document.documentElement.setAttribute('data-theme', value), theme);
    await page.locator('input[type="file"]').setInputFiles(image);
    await expect(page.locator('.visual-catalog-banner')).toContainText('No reliable product subject was recognized');
    await expect(page.locator('.visual-item-chip')).toHaveCount(0);
    await expect(page.getByText(/\d+% Match/)).toHaveCount(0);
  });
}
const image = {
  name: 'look.png', mimeType: 'image/png',
  buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aVt8AAAAASUVORK5CYII=', 'base64'),
};

for (const theme of ['light', 'dark']) {
  test(`ambiguous clothing photo offers a blazer choice in ${theme} mode`, async ({ page }) => {
    const blazer: VisualSearchDetectedItem = {
      ...items[0], id: 'candidate-suit-jacket-blazer', label: 'Suit jacket / blazer',
      confidence: null,
    };
    let requests: number = 0;
    await page.route('**/api/products/visual-search/', route => {
      requests += 1;
      return route.fulfill({ json: {
        ...analysis(0), detected_items: [blazer],
        selection_required: requests === 1,
        selected_item_id: requests === 1 ? null : blazer.id,
        selected_item: requests === 1 ? null : blazer,
        message: requests === 1
          ? 'Possible items found. Choose what you want to search for.'
          : 'Searching your selected item: Suit jacket / blazer, but no relevant catalog items were found.',
      } satisfies VisualSearchResponse });
    });
    await page.goto('/shop', { waitUntil: 'domcontentloaded' });
    await page.evaluate(value => document.documentElement.setAttribute('data-theme', value), theme);
    await page.locator('input[type="file"]').setInputFiles(image);
    await expect(page.getByRole('heading', { name: 'Choose what to look for' })).toBeVisible();
    await expect(page.locator('.visual-item-chip.active')).toHaveCount(0);
    await page.getByRole('button', { name: 'Suit jacket / blazer', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'No matching products yet' })).toBeVisible();
    await expect(page.locator('.visual-item-chip.active')).toHaveText('Suit jacket / blazer');
    await expect(page.locator('.visual-catalog-banner')).toContainText('Searching your selected item:');
  });
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/**', route => {
    const path: string = new URL(route.request().url()).pathname;
    if (path === '/api/me') return route.fulfill({ status: 401, json: { detail: 'Sign in required' } });
    return route.fulfill({ json: { count: 0, results: [], pages: 1 } });
  });
});

test('switching a detected item resubmits the source image', async ({ page }) => {
  let requests: number = 0;
  await page.route('**/api/products/visual-search/', route => {
    requests += 1;
    expect(route.request().postDataBuffer()?.toString()).toContain('filename="look.png"');
    return route.fulfill({ json: analysis(requests === 1 ? 0 : 1) });
  });
  await page.goto('/shop', { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="file"]').setInputFiles(image);
  await expect(page.locator('.visual-item-chip.active')).toHaveText('Jacket');
  await page.getByRole('button', { name: 'Shoes', exact: true }).click();
  await expect(page.locator('.visual-item-chip.active')).toHaveText('Shoes');
  expect(requests).toBe(2);
  const pending = page.waitForResponse('**/api/products/visual-search/');
  await page.getByRole('button', { name: 'Jacket', exact: true }).click();
  await pending;
  await page.evaluate(() => new Promise<void>(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  }));
  // The backend may choose a different reliable subject than the requested ID.
  await expect(page.locator('.visual-item-chip.active')).toHaveText('Shoes');
});

test('clearing a search ignores its late item-selection response', async ({ page }) => {
  let release: () => void = () => {};
  const pending: Promise<void> = new Promise(resolve => { release = resolve; });
  let requests: number = 0;
  await page.route('**/api/products/visual-search/', async route => {
    requests += 1;
    if (requests > 1) await pending;
    await route.fulfill({ json: analysis(requests === 1 ? 0 : 1) });
  });
  await page.goto('/shop', { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="file"]').setInputFiles(image);
  await page.getByRole('button', { name: 'Shoes', exact: true }).click();
  await expect.poll(() => requests).toBe(2);
  await page.getByRole('button', { name: 'Clear', exact: true }).click();
  const response = page.waitForResponse('**/api/products/visual-search/');
  release();
  await response;
  await expect(page).toHaveURL(/\/shop$/);
  await page.evaluate(() => new Promise<void>(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  }));
  await page.evaluate(() => window.history.pushState(null, '', '/shop?visual=1'));
  await expect(page.locator('.visual-catalog-banner')).toHaveCount(0);
});

test('visual upload errors are visible and can be retried', async ({ page }) => {
  let attempts: number = 0;
  await page.route('**/api/products/visual-search/', route => {
    attempts += 1;
    return route.fulfill({
      status: 503, json: { detail: 'Image search is temporarily unavailable.' },
    });
  });
  await page.goto('/shop', { waitUntil: 'domcontentloaded' });
  await page.locator('input[type="file"]').setInputFiles(image);
  await expect(page.locator('main').getByRole('alert')).toContainText('Image search is temporarily unavailable.');
  await page.locator('input[type="file"]').setInputFiles(image);
  await expect.poll(() => attempts).toBe(2);
});

test('reload discards unusable visual snapshots', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    sessionStorage.setItem('proace_visual_search_session', JSON.stringify({
      analysis: { results: {}, detected_items: [] }, selectedItemId: '0',
    }));
  });
  await page.goto('/shop?visual=1', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('main h1')).toBeVisible();
  await expect(page.locator('.visual-catalog-banner')).toHaveCount(0);
  expect(errors).toEqual([]);
});
