import { expect, test } from "@playwright/test";
import { enter, enteredAs } from "./helpers";

test("名前を入れると入室できる", async ({ page }) => {
  await enter(page, "はじめてのひと");

  await expect(page).toHaveURL("/");
  await enteredAs(page, "はじめてのひと");
});

test("入室していなければログイン画面に戻される", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL("/login");
});

test("退出するとログイン画面に戻り、そのままでは入り直せない", async ({
  page,
}) => {
  await enter(page, "でていくひと");
  await enteredAs(page, "でていくひと");

  await page.getByRole("button", { name: "退出する" }).click();

  await expect(page).toHaveURL("/login");
  // Cookie が消えていないと、ここでホームに入れてしまう
  await page.goto("/");
  await expect(page).toHaveURL("/login");
});

test("一度使った名前でも入り直せる", async ({ page }) => {
  // 1 回目は login が 404 になり signup に回る。2 回目は login で通る。
  // どちらも同じ操作で入れること
  await enter(page, "またくるひと");
  await enteredAs(page, "またくるひと");
  await page.getByRole("button", { name: "退出する" }).click();
  await expect(page).toHaveURL("/login");

  await enter(page, "またくるひと");

  await enteredAs(page, "またくるひと");
});

test("上限を超えた名前では入室ボタンが押せない", async ({ page }) => {
  await page.goto("/login");
  const name = page.getByLabel("ユーザー名");
  const submit = page.getByRole("button", { name: "入室する" });

  await name.fill("あ".repeat(33));
  await expect(submit).toBeDisabled();

  await name.fill("あ".repeat(32));
  await expect(submit).toBeEnabled();
});
