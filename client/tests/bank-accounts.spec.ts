import { expect, test } from '@playwright/test';

type Account = { id: number; bank_name: string; account_holder_name: string; account_last4: string; routing_last4: string; is_default: boolean };

test('bank account cards support modal creation, edit, default and deletion', async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem('proace-theme', 'light'));
  let accounts: Account[] = [];
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ json: { id: 7, email: 'seller@test.com', first_name: 'Seller' } });
    if (path.startsWith('/api/bank-accounts')) {
      if (request.method() === 'POST') {
        const values = request.postDataJSON() as { bank_name: string; account_holder_name: string; account_number: string; routing_number: string };
        const account: Account = { id: accounts.length + 1, bank_name: values.bank_name, account_holder_name: values.account_holder_name, account_last4: values.account_number.slice(-4), routing_last4: values.routing_number.slice(-4), is_default: !accounts.length };
        accounts.push(account);
        return route.fulfill({ json: account });
      }
      const id = Number(path.split('/').at(-1));
      if (request.method() === 'PATCH') {
        const values = request.postDataJSON() as Partial<Account>;
        if (values.is_default) accounts = accounts.map(account => ({ ...account, is_default: false }));
        accounts = accounts.map(account => account.id === id ? { ...account, ...values } : account);
        return route.fulfill({ json: accounts.find(account => account.id === id) });
      }
      if (request.method() === 'DELETE') {
        accounts = accounts.filter(account => account.id !== id);
        return route.fulfill({ status: 204 });
      }
      return route.fulfill({ json: accounts });
    }
    if (path === '/api/orders') return route.fulfill({ json: { count: 0, results: [] } });
    if (path === '/api/wallet') return route.fulfill({ json: { count: 0, balance: '0.00', transactions: [] } });
    if (path === '/api/cart') return route.fulfill({ json: { items: [], subtotal: '0', total: '0' } });
    return route.fulfill({ json: [] });
  });
  await page.goto('/account/payout-accounts');
  await page.getByRole('button', { name: 'Add bank account', exact: true }).click();
  const addDialog = page.getByRole('dialog', { name: 'Add bank account' });
  await addDialog.getByLabel('Bank name', { exact: true }).fill('Example Bank');
  await addDialog.getByLabel('Account holder', { exact: true }).fill('Seller Owner');
  await addDialog.getByLabel('Account number', { exact: true }).fill('1234567890');
  await addDialog.getByLabel('Routing number', { exact: true }).fill('123456789');
  await addDialog.getByRole('button', { name: 'Save bank account' }).click();
  await expect(page.getByText('Payout account saved securely.')).toBeVisible();
  await expect(page.locator('.bank-account-card strong').filter({hasText: 'Example Bank'})).toBeVisible();
  await expect(page.getByText('Account ••••7890 · Routing ••••6789')).toBeVisible();
  const bankSearch = page.getByPlaceholder('Search bank, account holder, or last 4 digits…');
  await bankSearch.fill('no matching account');
  await expect(page.getByRole('heading', {name: 'No bank accounts found'})).toBeVisible();
  await page.getByRole('button', {name: 'Clear filters'}).click();
  await expect(page.locator('.bank-account-card')).toHaveCount(1);
  await page.getByLabel('Account preference').selectOption('default');
  await expect(page.locator('.bank-account-card')).toHaveCount(1);
  await page.getByRole('button', {name: 'Clear filters'}).click();

  await page.goto('/account');
  await expect(page.getByRole('link', { name: 'Payout accounts' }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Payout accounts' }).first().click();
  await expect(page).toHaveURL(/\/account\/payout-accounts$/);
  await expect(page.locator('.bank-account-card strong').filter({hasText: 'Example Bank'})).toBeVisible();
  await page.getByRole('button', { name: 'Switch to dark mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('.bank-account-card strong').filter({hasText: 'Example Bank'})).toBeVisible();
  await page.locator('.payout-accounts-page').screenshot({path: testInfo.outputPath('payout-accounts-dark.png')});
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await page.locator('.payout-accounts-page').screenshot({path: testInfo.outputPath('payout-accounts-light.png')});
  await expect(page.getByText('Default bank account', {exact: true})).toBeVisible();
  await page.getByText('Actions', {exact: true}).click();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  const editDialog = page.getByRole('dialog', { name: 'Edit bank account' });
  await editDialog.getByLabel('Bank name', { exact: true }).fill('Renamed Bank');
  await editDialog.getByRole('button', { name: 'Save bank account' }).click();
  await expect(page.locator('.bank-account-card strong').filter({hasText: 'Renamed Bank'})).toBeVisible();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No bank accounts found' })).toBeVisible();
});

test('Stripe transfer destinations are saved without exposing their full account IDs', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('proace-theme', 'light'));
  let destinations: Array<{ id: number; label: string; account_id_last4: string; is_default: boolean }> = [];
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ json: { id: 7, email: 'seller@test.com', first_name: 'Seller' } });
    if (path.startsWith('/api/stripe-payout-destinations')) {
      if (request.method() === 'POST') {
        const values = request.postDataJSON() as { label: string; stripe_account_id: string; is_default: boolean };
        const destination = {
          id: 19,
          label: values.label,
          account_id_last4: values.stripe_account_id.slice(-4),
          is_default: values.is_default || !destinations.length,
        };
        destinations = [destination];
        return route.fulfill({ status: 201, json: destination });
      }
      return route.fulfill({ json: destinations });
    }
    if (path.startsWith('/api/bank-accounts')) return route.fulfill({ json: [] });
    if (path === '/api/cart') return route.fulfill({ json: { items: [], subtotal: '0', total: '0' } });
    return route.fulfill({ json: [] });
  });

  await page.goto('/account/payout-accounts');
  await expect(page.getByRole('link', { name: 'Explore the shop' })).toHaveCount(0);
  await expect(page.locator('.bank-accounts').getByLabel('Search accounts')).toHaveCount(0);
  await page.getByRole('button', { name: 'Add Stripe account', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Add Stripe account' });
  await dialog.getByLabel('Account label').fill('ProAce treasury transfers');
  await dialog.getByLabel('Stripe connected account ID').fill('acct_1234567890ABCDE');
  await dialog.getByRole('button', { name: 'Save Stripe account' }).click();

  await expect(page.getByText('Stripe destination saved securely.')).toBeVisible();
  const stripeSearch = page.getByPlaceholder('Search label or account’s last 4 characters…');
  await stripeSearch.fill('does not match');
  await expect(page.getByRole('heading', {name: 'No matching Stripe accounts'})).toBeVisible();
  await page.getByRole('button', {name: 'Clear filters'}).click();
  await expect(page.locator('.stripe-destination-card')).toHaveCount(1);

  await expect(page.locator('.stripe-destination-card strong').filter({hasText: 'ProAce treasury transfers'})).toBeVisible();
  await expect(page.getByText('Connected account · …BCDE')).toBeVisible();
  await expect(page.getByText('acct_1234567890ABCDE')).toHaveCount(0);
});

test('Stripe return opens confirmed order instead of checkout', async ({ page }) => {
  let confirmations = 0;
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({ json: { id: 7, email: 'buyer@test.com', first_name: 'Buyer' } });
    if (path === '/api/checkout/wallet-confirm') {
      confirmations += 1;
      expect(route.request().postDataJSON()).toEqual({ session_id: 'cs_fixture' });
      if (confirmations === 1) return route.fulfill({ status: 503, json: { detail: 'Confirmation is still processing.' } });
      return route.fulfill({ json: { id: 744 } });
    }
    if (path === '/api/cart') return route.fulfill({ json: { items: [], subtotal: '0', total: '0' } });
    if (path === '/api/orders/744') return route.fulfill({ status: 404, json: { detail: 'Fixture order detail' } });
    return route.fulfill({ json: [] });
  });
  await page.goto('/orders/stripe-return?session_id=cs_fixture');
  await expect(page.getByText('Confirmation is still processing.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page).toHaveURL(/\/orders\/744\?placed=true$/);
  expect(confirmations).toBe(2);
});

test('changing a default account persists through refresh and prevents overlapping actions', async ({page}) => {
  let updates = 0;
  const deferred: {release?: () => void} = {};
  let accounts: Account[] = [
    {id: 1, bank_name: 'First bank', account_holder_name: 'Owner', account_last4: '1111', routing_last4: '1111', is_default: true},
    {id: 2, bank_name: 'Second bank', account_holder_name: 'Owner', account_last4: '2222', routing_last4: '2222', is_default: false},
  ];
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (path === '/api/me') return route.fulfill({json: {id: 7, email: 'owner@test.com', first_name: 'Owner'}});
    if (path === '/api/bank-accounts/2' && route.request().method() === 'PATCH') {
      updates += 1;
      await new Promise<void>(resolve => { deferred.release = resolve; });
      accounts = accounts.map(account => ({...account, is_default: account.id === 2}));
      return route.fulfill({json: accounts[1]});
    }
    if (path === '/api/bank-accounts') return route.fulfill({json: accounts});
    if (path === '/api/stripe-payout-destinations') return route.fulfill({json: []});
    if (path.includes('notifications')) return route.fulfill({json: {unread: 0, total: 0}});
    if (path === '/api/orders') return route.fulfill({json: {count: 0, results: []}});
    if (path === '/api/wallet') return route.fulfill({json: {count: 0, balance: '0.00', transactions: []}});
    if (path === '/api/cart') return route.fulfill({json: {items: [], subtotal: '0', total: '0'}});
    return route.fulfill({json: []});
  });
  await page.goto('/account/payout-accounts');
  const second = page.locator('.bank-account-card').filter({hasText: 'Second bank'});
  await second.getByText('Actions', {exact: true}).click();
  const makeDefault = second.getByRole('button', {name: 'Set as default'});
  await makeDefault.click();
  await expect(makeDefault).toBeDisabled();
  await expect.poll(() => updates).toBe(1);
  deferred.release?.();
  await expect(second.getByText('Default bank account', {exact: true})).toBeVisible();
  await expect(page.getByText('Default bank account', {exact: true})).toHaveCount(1);
  expect(updates).toBe(1);
  await page.reload();
  await expect(page.locator('.bank-account-card').filter({hasText: 'Second bank'}).getByText('Default bank account', {exact: true})).toBeVisible();
});
