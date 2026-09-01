import { describe, expect, test } from "vitest";
import { formatTime } from "./time";

describe("formatTime", () => {
  test("UTC のオフセットを見ている人の時刻に直す", () => {
    // テストは TZ=Asia/Tokyo で走る。オフセットを読み落とすと 15:42 になる
    expect(formatTime("2026-08-30T06:42:48.538588+00:00")).toBe("15:42");
  });

  test("日付は出さず、時と分だけを出す", () => {
    expect(formatTime("2026-08-30T06:42:48.538588+00:00")).toMatch(
      /^\d{2}:\d{2}$/,
    );
  });
});
