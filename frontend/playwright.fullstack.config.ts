import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = 3200;
const API_PORT = 8702;
const API = `http://127.0.0.1:${API_PORT}`;
const ROOT = path.resolve(__dirname, "../backend/.fullstack");
const PYTHON = process.env.FULLSTACK_PYTHON ?? ".venv/bin/python";

export const FULLSTACK_ENV = {
  NBA_DATABASE_URL:
    process.env.NBA_FULLSTACK_DATABASE_URL ?? "postgresql+psycopg:///nba_intelligence_fullstack",
  NBA_FULLSTACK_DIR: ROOT,
  NBA_FULLSTACK_CLOCK: path.join(ROOT, "clock"),
  NBA_ARTIFACTS_DIR: path.join(ROOT, "artifacts"),
  NBA_LOG_LEVEL: "WARNING",
};

export default defineConfig({
  testDir: "tests/fullstack",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 180_000,
  outputDir: "test-results/fullstack",
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never", outputFolder: "playwright-report-fullstack" }]]
    : "list",
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    contextOptions: { reducedMotion: "reduce" },
  },
  webServer: [
    {
      command: `${PYTHON} -m tests.fullstack.harness seed && ${PYTHON} -m uvicorn --factory tests.fullstack.app:build --port ${API_PORT}`,
      cwd: "../backend",
      url: `${API}/api/v1/health`,
      env: FULLSTACK_ENV,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run build && npm run start -- -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}/about`,
      env: { API_INTERNAL_URL: API, NEXT_DIST_DIR: ".next-fullstack" },
      reuseExistingServer: false,
      timeout: 240_000,
    },
  ],
});
