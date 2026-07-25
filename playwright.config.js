const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['github']] : 'list',
  use: {
    baseURL: process.env.DRC_E2E_BASE_URL || 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    { name: 'chromium-desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'chromium-mobile', use: { ...devices['Pixel 7'] } }
  ],
  webServer: process.env.CI ? undefined : {
    command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env',
    url: 'http://127.0.0.1:8000/health/live',
    reuseExistingServer: true,
    timeout: 120_000
  }
});
