import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // `e2e/*.spec.ts` は Playwright が動かす。Vitest の既定は `.spec.` も
    // 拾うので、拡張子で持ち場を分ける
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
