import { expect, test } from "@playwright/test";
import { ROOM_NAME, enter, listed, roomView, send, streaming } from "./helpers";

test("入室するとチャットルームに着く", async ({ page }) => {
  await enter(page, "つくひと");

  await expect(page.getByRole("heading", { name: ROOM_NAME })).toBeVisible();
  await expect(page.getByLabel("メッセージ")).toBeVisible();
});

test("送ったメッセージが一覧に出る", async ({ page }) => {
  await enter(page, "おくるひと");
  await streaming(page);

  await send(page, "おくるひとの一言");

  await listed(page, "おくるひとの一言");
  // 自分の送信は手元と WebSocket の両方から来る。並ぶのは 1 通だけ
  await expect(
    page.getByRole("listitem").filter({ hasText: "おくるひとの一言" }),
  ).toHaveCount(1);
  // 送ったら入力欄は空に戻る
  await expect(page.getByLabel("メッセージ")).toHaveValue("");
});

test("別の人の発言が、名前つきでその場で届く", async ({ page, browser }) => {
  await enter(page, "きくひと");
  await streaming(page);

  const otherContext = await browser.newContext();
  const other = await otherContext.newPage();
  await enter(other, "はなすひと");
  await streaming(other);

  // 画面を触っていない側に、WebSocket 越しに届く。
  // 誰の発言かが分かるよう、相手の発言には名前が添う
  await send(other, "そちらは聞こえますか");
  await expect(
    page.getByRole("listitem").filter({ hasText: "そちらは聞こえますか" }),
  ).toContainText("はなすひと");

  await send(page, "聞こえています");
  await expect(
    other.getByRole("listitem").filter({ hasText: "聞こえています" }),
  ).toContainText("きくひと");

  await otherContext.close();
});

test("入り直しても発言が残っている", async ({ page }) => {
  await enter(page, "もどるひと");
  await streaming(page);
  await send(page, "もどるひとの一言");
  await listed(page, "もどるひとの一言");

  await page.reload();

  // 開いた直後の取得で、それまでのやりとりが並ぶ
  await listed(page, "もどるひとの一言");
});

test("上限を超えた本文は送れない", async ({ page }) => {
  await enter(page, "ながいひと");
  const input = page.getByLabel("メッセージ");
  const submit = page.getByRole("button", { name: "送信" });

  await input.fill("あ".repeat(1001));

  await expect(submit).toBeDisabled();
  await expect(page.getByText("1 文字多いです")).toBeVisible();
});

test("上限ちょうどの本文は送れる", async ({ page }) => {
  await enter(page, "ちょうどのひと");

  await page.getByLabel("メッセージ").fill("あ".repeat(1000));

  await expect(page.getByRole("button", { name: "送信" })).toBeEnabled();
});

test("空白だけの本文は送れない", async ({ page }) => {
  await enter(page, "からのひと");

  await page.getByLabel("メッセージ").fill("   ");

  await expect(page.getByRole("button", { name: "送信" })).toBeDisabled();
});

test("Enter で送り、Shift+Enter で改行する", async ({ page }) => {
  await enter(page, "かいぎょうのひと");
  await streaming(page);
  const input = page.getByLabel("メッセージ");

  await input.fill("いち");
  await input.press("Shift+Enter");
  await input.pressSequentially("に");
  await expect(input).toHaveValue("いち\nに");

  await input.press("Enter");

  await listed(page, "いち\nに");
  await expect(input).toHaveValue("");
});

test("送信中に打ち足した文字が消えない", async ({ page }) => {
  await enter(page, "うちたすひと");
  await streaming(page);

  // 応答を遅らせて、待っている間に打てるようにする
  await page.route("**/messages", async (route) => {
    if (route.request().method() === "POST") {
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue();
  });

  const input = page.getByLabel("メッセージ");
  await input.fill("さきの一言");
  await input.press("Enter");
  await input.pressSequentially("あとの一言");

  await listed(page, "さきの一言");
  await expect(input).toHaveValue("さきの一言あとの一言");
});

test("読み返している間は、新着で下に飛ばされない", async ({
  page,
  browser,
}) => {
  await enter(page, "よみかえすひと");
  await streaming(page);
  const other = await (await browser.newContext()).newPage();
  await enter(other, "はなしかけるひと");
  await streaming(other);

  // 一覧がはみ出すまで積む
  for (let index = 0; index < 20; index += 1) {
    await send(page, `つみあげ ${index}`);
  }
  await listed(page, "つみあげ 19");

  const view = roomView(page);
  await view.evaluate((element) => {
    element.scrollTop = 0;
  });
  await expect.poll(() => view.evaluate((e) => e.scrollTop)).toBe(0);

  await send(other, "よみかえし中の割り込み");

  await listed(page, "よみかえし中の割り込み");
  // 読んでいた位置に留まること
  expect(await view.evaluate((element) => element.scrollTop)).toBe(0);
});

test("下端を見ているときは、新着を追いかける", async ({ page, browser }) => {
  await enter(page, "おいかけるひと");
  await streaming(page);
  const other = await (await browser.newContext()).newPage();
  await enter(other, "つづけるひと");
  await streaming(other);

  for (let index = 0; index < 20; index += 1) {
    await send(page, `おいかけ ${index}`);
  }
  await listed(page, "おいかけ 19");

  await send(other, "下端への割り込み");

  await listed(page, "下端への割り込み");
  const view = roomView(page);
  await expect
    .poll(() =>
      view.evaluate(
        (element) =>
          element.scrollHeight - element.scrollTop - element.clientHeight,
      ),
    )
    .toBeLessThanOrEqual(1);
});

test("発言が増えても、ヘッダーと入力欄が画面に残る", async ({ page }) => {
  await enter(page, "つみあげるひと");
  await streaming(page);

  for (let index = 0; index < 20; index += 1) {
    await send(page, `画面いっぱい ${index}`);
  }
  await listed(page, "画面いっぱい 19");

  // 伸びるのは一覧の中だけ。文書が伸びると入力欄が画面外へ流れていく
  const documentGrew = await page.evaluate(
    () =>
      document.documentElement.scrollHeight >
      document.documentElement.clientHeight,
  );
  expect(documentGrew).toBe(false);
  await expect(page.getByRole("banner")).toBeInViewport();
  await expect(page.getByLabel("メッセージ")).toBeInViewport();
});

test("読み返している最中でも、自分の発言は見えるところに出る", async ({
  page,
}) => {
  await enter(page, "よみつつおくるひと");
  await streaming(page);

  for (let index = 0; index < 20; index += 1) {
    await send(page, `さかのぼり ${index}`);
  }
  await listed(page, "さかのぼり 19");

  const view = roomView(page);
  await view.evaluate((element) => {
    element.scrollTop = 0;
  });
  await expect
    .poll(() => view.evaluate((element) => element.scrollTop))
    .toBe(0);

  await send(page, "よみかえし中に送った一言");
  await listed(page, "よみかえし中に送った一言");

  // 送ったのに画面外だと、送れたのかどうかが分からない。
  // 一覧の中に限る。送信中は入力欄にも同じ文字が残っている
  await expect(
    page.getByRole("listitem").filter({ hasText: "よみかえし中に送った一言" }),
  ).toBeInViewport();
});
