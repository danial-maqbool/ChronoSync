import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  workers: 1,
  timeout: 90000,
  use: {
    baseURL: "http://127.0.0.1:8766",
    headless: true,
    actionTimeout: 10000,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: "python ../run.py",
    url: "http://127.0.0.1:8766/api/health",
    reuseExistingServer: false,
    env: {
      CHRONOSYNC_PORT: "8766",
      CHRONOSYNC_DATA_DIR: "data/e2e-" + Date.now(),
    },
    timeout: 30000,
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "../docs/validation/playwright.json" }],
  ],
});
