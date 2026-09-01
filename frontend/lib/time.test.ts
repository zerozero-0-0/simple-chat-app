import { describe, expect, test } from "vitest";
import { formatTime } from "./time";

describe("formatTime", () => {
  test("UTC のオフセットを見ている人の時刻に直す", () => {
    // テストは TZ=Asia/Tokyo で走る。オフセットを読み落とすと 15:42 になる
    expect(formatTime("2026-08-30T06:42:48.538588+00:00")).toBe("15:42");
  });

  test("読み手の言語設定に関わらず 24 時間表記で出す", () => {
    // 既定の書式は環境で変わる。en-US では "03:42 PM" になる
    expect(formatTime("2026-08-30T06:42:48.538588+00:00")).toMatch(
      /^\d{2}:\d{2}$/,
    );
  });
});
