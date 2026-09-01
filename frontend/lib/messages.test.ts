import { describe, expect, test } from "vitest";
import { isMyNewMessage, mergeMessages } from "./messages";
import type { Message } from "./types";

function message(id: number, senderId = "u1"): Message {
  return {
    id,
    client_message_id: `c${id}`,
    body: `body${id}`,
    created_at: "2026-08-30T04:42:48.538588+00:00",
    sender: { public_id: senderId, display_name: "アリス" },
  };
}

describe("mergeMessages", () => {
  test("同じ id は 1 通にまとまる", () => {
    // WebSocket で届いたものが取り直しでもう一度来る
    const merged = mergeMessages([message(1), message(2)], [message(2)]);

    expect(merged.map((m) => m.id)).toEqual([1, 2]);
  });

  test("届いた順が前後しても id の順に並ぶ", () => {
    const merged = mergeMessages([message(3)], [message(1), message(2)]);

    expect(merged.map((m) => m.id)).toEqual([1, 2, 3]);
  });

  test("元の一覧を書き換えない", () => {
    const current = [message(1)];

    mergeMessages(current, [message(2)]);

    expect(current.map((m) => m.id)).toEqual([1]);
  });

  test("空の一覧にも足せる", () => {
    expect(mergeMessages([], [message(1)]).map((m) => m.id)).toEqual([1]);
  });
});

describe("isMyNewMessage", () => {
  test("自分の発言が末尾に増えたら真", () => {
    expect(isMyNewMessage([message(1), message(2)], 1, "u1")).toBe(true);
  });

  test("増えたのが他の人なら偽", () => {
    expect(isMyNewMessage([message(1), message(2, "u2")], 1, "u1")).toBe(false);
  });

  test("末尾が変わっていなければ偽", () => {
    // つなぎ直しの取り直しが空でも、一覧は新しい配列で作り直される。
    // 末尾が自分のままでも、増えていないので追いかけない
    expect(isMyNewMessage([message(1), message(2)], 2, "u1")).toBe(false);
  });

  test("初めての 1 通も、自分のものなら真", () => {
    expect(isMyNewMessage([message(1)], undefined, "u1")).toBe(true);
  });

  test("空の一覧は偽", () => {
    expect(isMyNewMessage([], undefined, "u1")).toBe(false);
  });
});
