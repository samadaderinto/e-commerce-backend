import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { StoreProfile } from '../src/lib/types';

async function photo(page: Page, width: number, height: number): Promise<Buffer> {
  const encoded = await page.evaluate(({ width: imageWidth, height: imageHeight }): string => {
    const canvas = document.createElement('canvas');
    canvas.width = imageWidth;
    canvas.height = imageHeight;
    const context = canvas.getContext('2d')!;
    context.fillStyle = '#285e43';
    context.fillRect(0, 0, imageWidth / 2, imageHeight);
    context.fillStyle = '#eaa267';
    context.fillRect(imageWidth / 2, 0, imageWidth / 2, imageHeight);
    return canvas.toDataURL('image/png').split(',')[1];
  }, { width, height });
  return Buffer.from(encoded, 'base64');
}

test('store images crop, preview, retry, persist and remove without submitting other settings', async ({ page }, testInfo) => {
  let profile: StoreProfile = { bio: 'Made with care', email: 'seller@test.com' };
  let failUpload = true;
  let uploads = 0;
  let settingsWrites = 0;
  const files: Partial<Record<'avatar' | 'banner', Buffer>> = {};
  const sizes: { kind: string; width: number; height: number }[] = [];
  const store = { id: 1, name: 'Apex Athletics', username: 'apex', status: 'active' };

  await page.route('**/api/**', async (route): Promise<void> => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    const kind = path.endsWith('/avatar') ? 'avatar' : 'banner';
    if (path.includes('/profile-images/')) {
      if (request.method() === 'DELETE') {
        profile = { ...profile, [`${kind}_url`]: '' };
      } else {
        uploads += 1;
        const body = request.postDataBuffer()!;
        expect(request.headers()['content-type']).toContain('multipart/form-data; boundary=');
        const start = body.indexOf(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
        expect(start).toBeGreaterThan(0);
        const cropped = body.subarray(start, body.lastIndexOf(Buffer.from('\r\n--')));
        sizes.push({ kind, width: cropped.readUInt32BE(16), height: cropped.readUInt32BE(20) });
        if (failUpload) {
          failUpload = false;
          await route.fulfill({ status: 503, json: { detail: 'Upload temporarily unavailable. Please retry.' } });
          return;
        }
        files[kind] = cropped;
        profile = { ...profile, [`${kind}_url`]: `/api/stores/1/public/images/${kind}?v=${uploads}` };
      }
      await route.fulfill({ json: profile });
      return;
    }
    if (path.includes('/public/images/')) {
      await route.fulfill({ contentType: 'image/png', body: files[kind] || Buffer.alloc(0) });
      return;
    }
    if (request.method() !== 'GET') settingsWrites += 1;
    let json: unknown = {};
    if (path === '/api/me') json = { id: 7, first_name: 'Seller', email: 'seller@test.com' };
    else if (path === '/api/stores') json = { count: 1, results: [store] };
    else if (path === '/api/stores/1') json = store;
    else if (path === '/api/stores/1/profile') json = profile;
    else if (path === '/api/stores/1/pickup-address') json = {
      address: '1 Main St', city: 'Tampa', state: 'FL', country: 'US', zip: '33602',
    };
    else if (path === '/api/cart') json = { items: [], subtotal: '0', shipping: '0', total: '0' };
    else if (path === '/api/wishlist') json = [];
    await route.fulfill({ json });
  });

  await page.goto('/merchant/settings', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Store branding' })).toBeVisible();
  const small = await photo(page, 100, 100);
  const original = await photo(page, 2048, 1024);
  const profilePicker = page.getByLabel('Upload profile image', { exact: true });
  await profilePicker.setInputFiles({ name: 'small.png', mimeType: 'image/png', buffer: small });
  await expect(page.getByRole('alert').filter({ hasText: 'at least 512 × 512' })).toContainText('at least 512 × 512');
  expect(uploads).toBe(0);

  await profilePicker.setInputFiles({ name: 'brand.png', mimeType: 'image/png', buffer: original });
  let dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('img', { name: 'Circular profile image preview' })).toHaveCSS('border-radius', '50%');
  await dialog.getByLabel('Zoom', { exact: true }).focus();
  await page.keyboard.press('End');
  await expect(dialog.getByLabel('Zoom', { exact: true })).toHaveValue('3');
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(uploads).toBe(0);

  await profilePicker.setInputFiles({ name: 'brand.png', mimeType: 'image/png', buffer: original });
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Horizontal position').focus();
  await page.keyboard.press('Home');
  await expect(dialog.getByLabel('Horizontal position')).toHaveValue('0');
  await page.screenshot({ path: `/private/tmp/proace-store-crop-${testInfo.project.name}.png` });
  await dialog.getByRole('button', { name: 'Save profile image', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('Please retry');
  await expect(dialog.getByLabel('Horizontal position')).toHaveValue('0');
  await dialog.getByRole('button', { name: 'Save profile image', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('img', { name: 'Apex Athletics profile image' })).toBeVisible();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('img', { name: 'Apex Athletics profile image' })).toBeVisible();

  await page.getByLabel('Upload banner', { exact: true }).setInputFiles({
    name: 'banner.png', mimeType: 'image/png', buffer: original,
  });
  dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('img', { name: 'Banner image preview' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Save banner', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('img', { name: 'Apex Athletics banner' })).toBeVisible();
  expect(sizes).toEqual([
    { kind: 'avatar', width: 512, height: 512 },
    { kind: 'avatar', width: 512, height: 512 },
    { kind: 'banner', width: 1600, height: 600 },
  ]);
  await page.getByRole('button', { name: 'Remove profile image' }).click();
  await expect(page.getByRole('img', { name: 'Apex Athletics profile image' })).toHaveCount(0);
  expect(settingsWrites).toBe(0);
  expect(await page.evaluate((): boolean => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
