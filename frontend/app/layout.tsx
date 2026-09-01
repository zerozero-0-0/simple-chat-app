import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "simple-chat-app",
  description: "LINE風の簡単なチャットアプリ",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ja" className="h-full antialiased">
      <body className="flex h-full flex-col">{children}</body>
    </html>
  );
}
