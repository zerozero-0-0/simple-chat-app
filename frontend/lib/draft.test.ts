import { describe, expect, test } from "vitest";
import { draftFor } from "./draft";

describe("draftFor", () => {
  test("同じ本文の送り直しは同じ id になる", () => {
    const first = draftFor(null, "やあ");

    expect(draftFor(first, "やあ").id).toBe(first.id);
  });

  test("本文を書き換えると別の id になる", () => {
    // 同じ id で送ると、サーバーは先に届いた本文を返して書き換えを捨てる
    const first = draftFor(null, "やあ");

    expect(draftFor(first, "やっぱりこんにちは").id).not.toBe(first.id);
  });

  test("送るたびに違う発言なら id も違う", () => {
    expect(draftFor(null, "いち").id).not.toBe(draftFor(null, "に").id);
  });

  test("本文をそのまま持つ", () => {
    expect(draftFor(null, "やあ").body).toBe("やあ");
  });
});
