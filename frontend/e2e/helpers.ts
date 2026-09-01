import { expect, type Page } from "@playwright/test";

/** バックエンドが起動時に 1 つだけ作る部屋。 */
export const ROOM_NAME = "みんなの部屋";

/** ログイン画面から名前を送って入室する。 */
export async function enter(page: Page, name: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("ユーザー名").fill(name);
  await page.getByRole("button", { name: "入室する" }).click();
}

/** チャットルームに着いていること。名前はヘッダーに出る。 */
export function enteredAs(page: Page, name: string) {
  return expect(page.getByRole("banner")).toContainText(name);
}

/**
 * WebSocket がつながるまで待つ。
 *
 * つながる前に相手が送ると、その 1 通は取り直しまで届かない。
 * 受信の確認では、待ってから送らせる。
 *
 * `toBeHidden` は要素が無いときも通るので、先にヘッダーの描画を待つ。
 * 「つなぎ直しています」はヘッダーの中にあり、つながると消える。
 */
export async function streaming(page: Page): Promise<void> {
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByText("つなぎ直しています")).toBeHidden();
}

/** メッセージを送る。 */
export async function send(page: Page, body: string): Promise<void> {
  await page.getByLabel("メッセージ").fill(body);
  await page.getByRole("button", { name: "送信" }).click();
}

/** 一覧に出ていること。部屋は共通なので、本文はテストごとに変える。 */
export function listed(page: Page, body: string) {
  return expect(page.getByRole("list")).toContainText(body);
}

/** メッセージ一覧のスクロールする箱。 */
export function roomView(page: Page) {
  return page.getByRole("log", { name: "発言の一覧" });
}
