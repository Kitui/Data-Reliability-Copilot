const { test, expect } = require('@playwright/test');

const email = process.env.DRC_E2E_ADMIN_EMAIL || process.env.DRC_ADMIN_EMAIL || 'admin@drc.test';
const password = process.env.DRC_E2E_ADMIN_PASSWORD || process.env.DRC_ADMIN_PASSWORD || 'StrongPassword123!';

test('application loads with accessible login form', async ({ page }) => {
  await page.goto('/');
  const loginForm = page.locator('#loginForm');
  await expect(loginForm).toBeVisible();
  await expect(loginForm.locator('#loginEmail')).toBeVisible();
  await expect(loginForm.locator('#loginPassword')).toBeVisible();
  await expect(loginForm.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
});

test('administrator can sign in and open the application shell', async ({ page }) => {
  await page.goto('/');
  const loginForm = page.locator('#loginForm');
  await loginForm.locator('#loginEmail').fill(email);
  await loginForm.locator('#loginPassword').fill(password);
  await loginForm.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(loginForm).toBeHidden();
  await expect(page.locator('#mainContent')).toBeVisible();
});

test('health endpoints remain available', async ({ request }) => {
  const live = await request.get('/health/live');
  expect(live.ok()).toBeTruthy();

  const ready = await request.get('/health/ready');
  if (!ready.ok()) {
    console.log('Readiness response:', ready.status(), await ready.text());
  }
  expect(ready.ok()).toBeTruthy();
});
