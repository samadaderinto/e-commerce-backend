import { expect, test } from '@playwright/test';

test('Google account button submits the returned ID token to the same-origin API', async ({ page }) => {
  await page.route('https://accounts.google.com/gsi/client', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'text/javascript',
      body: `
        window.google = { accounts: { id: {
          initialize(config) { window.__googleCredentialCallback = config.callback; },
          renderButton(target, options) {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = options.text === 'signup_with' ? 'Sign up with Google' : 'Sign in with Google';
            button.addEventListener('click', () => window.__googleCredentialCallback({ credential: 'mock-google-id-token' }));
            target.appendChild(button);
          }
        } } };
      `,
    });
  });

  let submittedCredential = '';
  await page.route('**/api/auth/google*', async route => {
    submittedCredential = route.request().postDataJSON().credential;
    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Mock Google token rejection.' }),
    });
  });

  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in with Google' }).click();
  await expect(page.getByText('Mock Google token rejection.')).toBeVisible();
  expect(submittedCredential).toBe('mock-google-id-token');
});
