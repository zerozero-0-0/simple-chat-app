import { describe, expect, test } from "vitest";
import { mergeMessages } from "./messages";
import type { Message } from "./types";

function message(id: number, body = `body${id}`): Message {
  return {
    id,
    client_message_id: `c${id}`,
    body,
    created_at: "2026-08-30T04:42:48.538588+00:00",
    sender: { public_id: "u1", display_name: "アリス" },
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
