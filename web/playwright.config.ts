import { defineConfig, devices } from '@playwright/test'

// E2E_REAL=1: against the real API (uv run fele serve [--lcu]) through the dev server's /api proxy.
// Default (CI): the production build, with /api answered by e2e/mockApi.ts inside the browser.
const real = process.env.E2E_REAL === '1'
const port = 4173

export default defineConfig({
  testDir: 'e2e',
  testIgnore: real ? ['**/flow.spec.ts'] : [],
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: `http://localhost:${port}`, trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'phone', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: real ? `pnpm dev --port ${port} --strictPort` : `pnpm build && pnpm preview --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
