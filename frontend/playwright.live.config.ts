import { defineConfig, devices } from "@playwright/test";

// Checks against the real API and database; never run in CI. Start the backend first:
//   cd backend && .venv/bin/uvicorn --factory app.main:build --port 8000
// then: npx playwright test -c playwright.live.config.ts
const PORT = 3102;
const LIVE_API = process.env.LIVE_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "tests/live",
  workers: 1,
  reporter: "list",
  timeout: 180_000,
  use: { baseURL: `http://localhost:${PORT}`, ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
  webServer: {
    command: `npm run build && npm run start -- -p ${PORT}`,
    url: `http://localhost:${PORT}/about`,
    env: { API_INTERNAL_URL: LIVE_API, NEXT_DIST_DIR: ".next-live" },
    reuseExistingServer: true,
    timeout: 180_000,
  },
});
