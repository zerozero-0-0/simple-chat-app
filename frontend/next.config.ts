import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 画面の隅に出る Next の開発バッジを出さない。開発中の画面をそのまま
  // 見せたいときに邪魔になる。コンパイルエラーの表示はこれとは別に残る
  devIndicators: false,
};

export default nextConfig;
