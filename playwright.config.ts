import {defineConfig, devices} from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: 'test-results',
  reporter: [['list'], ['html', {open: 'never'}]],
  timeout: 45_000,
  workers: 1,
  use: {
    baseURL: process.env.NOVENA_E2E_BASE_URL || 'http://localhost:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {name: 'desktop', use: {...devices['Desktop Chrome'], viewport: {width: 1440, height: 900}}},
    {name: 'tablet', use: {...devices['Desktop Chrome'], viewport: {width: 1024, height: 768}}},
    {name: 'mobile', use: {...devices['Desktop Chrome'], viewport: {width: 390, height: 844}}},
  ],
});
