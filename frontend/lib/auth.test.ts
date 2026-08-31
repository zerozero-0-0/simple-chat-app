import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { ApiError } from "./api";
import * as api from "./api";
import { enter } from "./auth";
import type { User } from "./types";

const alice: User = {
  public_id: "u1",
  login_name: "alice",
  display_name: "alice",
};

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("enter", () => {
  test("既にいる名前なら login だけで入る", async () => {
    const logIn = vi.spyOn(api, "logIn").mockResolvedValue(alice);
    // 実装を与えないと本物の fetch が飛び、失敗がタイムアウトとして出る
    const signUp = vi
      .spyOn(api, "signUp")
      .mockRejectedValue(new Error("signUp は呼ばれてはいけない"));

    await expect(enter("alice")).resolves.toEqual(alice);

    expect(logIn).toHaveBeenCalledWith("alice");
    expect(signUp).not.toHaveBeenCalled();
  });

  test("まだ無い名前なら signup する", async () => {
    vi.spyOn(api, "logIn").mockRejectedValue(
      new ApiError(404, "この名前のユーザーはいません"),
    );
    const signUp = vi.spyOn(api, "signUp").mockResolvedValue(alice);

    await expect(enter("alice")).resolves.toEqual(alice);

    expect(signUp).toHaveBeenCalledWith("alice");
  });

  test("404 以外は握りつぶさない", async () => {
    vi.spyOn(api, "logIn").mockRejectedValue(new ApiError(500, "壊れました"));
    const signUp = vi
      .spyOn(api, "signUp")
      .mockRejectedValue(new Error("signUp は呼ばれてはいけない"));

    await expect(enter("alice")).rejects.toThrow("壊れました");

    expect(signUp).not.toHaveBeenCalled();
  });
});
