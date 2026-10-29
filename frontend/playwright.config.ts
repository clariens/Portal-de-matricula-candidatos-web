import { defineConfig } from "@playwright/test";

// E2E: o BFF real (uvicorn :8010) com o dublê do Lyceum de backend/tests/fake_lyceum.py, servindo o build de produção
// do front (mesma origem). O portal em si não tem modo de demonstração.
const py = process.platform === "win32" ? "..\\backend\\.venv\\Scripts\\python" : "../backend/.venv/bin/python";

export default defineConfig({
  testDir: "e2e",
  timeout: 240_000,
  expect: { timeout: 60_000 },
  use: { baseURL: "http://127.0.0.1:8010", locale: "pt-BR", trace: "retain-on-failure" },
  webServer: {
    command: `${py} -m uvicorn tests.e2e_app:app --port 8010 --app-dir ../backend`,
    url: "http://127.0.0.1:8010/api/v1/health",
    reuseExistingServer: false,
    env: { PORTAL_ENV_FILE: "__sem_env_no_e2e__", PORTAL_SESSION_SECRET: "e2e-segredo", PORTAL_COOKIE_SECURE: "false" },
  },
});
