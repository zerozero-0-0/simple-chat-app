import { describe, expect, test } from "vitest";
import { cleanName, countCharacters } from "./text";

describe("countCharacters", () => {
  test("日本語は見たままの数になる", () => {
    expect(countCharacters("さくら")).toBe(3);
  });

  test("絵文字を UTF-16 単位で数えない", () => {
    // String.length では 2 になり、サーバーの数え方とずれる
    expect("🌸".length).toBe(2);
    expect(countCharacters("🌸")).toBe(1);
  });

  test("空文字は 0", () => {
    expect(countCharacters("")).toBe(0);
  });
});

describe("cleanName", () => {
  test("前後の空白を落とす", () => {
    expect(cleanName("  alice  ")).toBe("alice");
  });

  test("中の空白は残す", () => {
    expect(cleanName("山田 太郎")).toBe("山田 太郎");
  });

  test("分解形を NFC に揃える", () => {
    const decomposed = "が".normalize("NFD");
    expect(decomposed).not.toBe("が");
    expect(cleanName(decomposed)).toBe("が");
  });

  test("整えてから数えると、サーバーと同じ 32 文字になる", () => {
    const decomposed = "が".repeat(32).normalize("NFD");
    expect(countCharacters(decomposed)).toBe(64);
    expect(countCharacters(cleanName(decomposed))).toBe(32);
  });
});
