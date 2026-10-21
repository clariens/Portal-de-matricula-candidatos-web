import { defineConfig } from "@playwright/test";

// E2E no modo mock: o BFF (uvicorn :8010) serve o build de produção do front (mesma origem).
const py = process.platform === "win32" ? "..\\backend\\.venv\\Scripts\\python" : "../backend/.venv/bin/python";

export default defineConfig({
  testDir: "e2e",
  timeout: 240_000,
  expect: { timeout: 60_000 },
  use: { baseURL: "http://127.0.0.1:8010", locale: "pt-BR", trace: "retain-on-failure" },
  webServer: {
    command: `${py} -m uvicorn app.main:app --port 8010 --app-dir ../backend`,
    url: "http://127.0.0.1:8010/api/v1/health",
    reuseExistingServer: false,
    env: { LYCEUM_MODE: "mock", PORTAL_SESSION_SECRET: "e2e-segredo", PORTAL_COOKIE_SECURE: "false" },
  },
});
