import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // `@/` の解決を tsconfig の paths に合わせる
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    // 時刻の表示は見ている人の地域で変わる。どこで走らせても同じ結果に
    // なるよう固定する
    env: { TZ: "Asia/Tokyo" },
    // `e2e/*.spec.ts` は Playwright が動かす。Vitest の既定は `.spec.` も
    // 拾うので、拡張子で持ち場を分ける
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
