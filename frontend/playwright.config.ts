import { defineConfig, devices } from "@playwright/test";

// 開発でいつも使う 3000 / 8000 とはずらす。E2E が開発中のサーバーや
// 開発用の DB に触らないようにするため
const WEB_PORT = 3100;
const API_PORT = 8100;

// 名前解決で ::1 と 127.0.0.1 のどちらに転ぶかが環境で変わるので、
// アドレスを直に指定する。
// 閉じたポートへの接続が拒否されずタイムアウトする環境 (WSL2 のミラー
// ネットワークなど) では、Playwright が起動前に打つ疎通確認が数分待つ。
// そのときは E2E_HOST=::1 を渡す
const HOST = process.env.E2E_HOST ?? "127.0.0.1";

// Cookie はポートを見ないので、ホストが同じならセッションはそのまま届く
const origin = (port: number) =>
  HOST.includes(":") ? `http://[${HOST}]:${port}` : `http://${HOST}:${port}`;
const WEB_URL = origin(WEB_PORT);
const API_URL = origin(API_PORT);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // 通ったことのある .only を CI に持ち込ませない
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  // CI では失敗した操作を追えるよう html レポートを残し、注釈を PR に出す
  reporter: process.env.CI
    ? [["html", { open: "never" }], ["github"]]
    : [["list"]],

  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
  },

  projects: [{ name: "chromium", use: devices["Desktop Chrome"] }],

  webServer: [
    {
      name: "api",
      // 毎回まっさらな DB で始める。前回のユーザーが残っていると結果が変わる
      command: `rm -f e2e.db && uv run uvicorn app.main:app --host ${HOST} --port ${API_PORT}`,
      cwd: "../backend",
      env: {
        APP_DATABASE_URL: "sqlite+aiosqlite:///e2e.db",
        APP_CORS_ORIGINS: JSON.stringify([WEB_URL]),
      },
      url: `${API_URL}/api/health`,
      reuseExistingServer: false,
    },
    {
      name: "web",
      // 本番と同じビルドを見る。`next dev` にしか無い挙動 (Strict Mode の
      // 二重実行、`allowedDevOrigins` の制限) を結果に混ぜないため。
      // `NEXT_PUBLIC_*` はビルド時に埋め込まれるので、build もここで走らせる
      command: `pnpm build && pnpm start --hostname ${HOST} --port ${WEB_PORT}`,
      env: { NEXT_PUBLIC_API_BASE_URL: API_URL },
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
