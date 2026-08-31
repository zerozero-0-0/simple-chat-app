import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  ApiError,
  fetchMessages,
  logIn,
  joinRoom,
  logOut,
  messageStreamUrl,
  sendMessage,
  signUp,
} from "./api";

/** 直近の `fetch` の呼ばれ方を覚えておくための差し替え。 */
function stubFetch(response: Response) {
  const spy = vi.fn(async () => response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function lastCall(spy: ReturnType<typeof stubFetch>) {
  const [url, init] = spy.mock.calls.at(-1) as unknown as [string, RequestInit];
  return { url, init };
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("送るリクエスト", () => {
  test("セッションの Cookie を送る", async () => {
    const spy = stubFetch(
      jsonResponse({ public_id: "u1", name: "みんなの部屋" }),
    );

    await joinRoom("r1");

    // 付け忘れると Cookie が飛ばず、すべて 401 になる
    expect(lastCall(spy).init.credentials).toBe("include");
  });

  test("signup と login は別のエンドポイントを叩く", async () => {
    const signUpSpy = stubFetch(jsonResponse({ public_id: "u1" }));
    await signUp("alice");
    expect(lastCall(signUpSpy).url).toBe(
      "http://localhost:8000/api/auth/signup",
    );

    const logInSpy = stubFetch(jsonResponse({ public_id: "u1" }));
    await logIn("alice");
    expect(lastCall(logInSpy).url).toBe("http://localhost:8000/api/auth/login");
  });

  test("入室は部屋の public_id を URL に載せて POST する", async () => {
    const spy = stubFetch(
      jsonResponse({ public_id: "r1", name: "みんなの部屋" }),
    );

    await joinRoom("r1");

    const { url, init } = lastCall(spy);
    expect(url).toBe("http://localhost:8000/api/rooms/r1/members");
    expect(init.method).toBe("POST");
  });

  test("本文がある要求だけ content-type を付ける", async () => {
    const withBody = stubFetch(jsonResponse({ id: 1 }));
    await sendMessage("r1", "c1", "やあ");
    expect(
      new Headers(lastCall(withBody).init.headers).get("content-type"),
    ).toBe("application/json");

    const withoutBody = stubFetch(jsonResponse([]));
    await fetchMessages("r1");
    expect(
      new Headers(lastCall(withoutBody).init.headers).get("content-type"),
    ).toBeNull();
  });

  test("after を渡すとカーソルとして載る", async () => {
    const spy = stubFetch(jsonResponse([]));

    await fetchMessages("r1", 12);

    expect(lastCall(spy).url).toBe(
      "http://localhost:8000/api/rooms/r1/messages?after=12",
    );
  });

  test("after を渡さなければ載せない", async () => {
    const spy = stubFetch(jsonResponse([]));

    await fetchMessages("r1");

    expect(lastCall(spy).url).toBe(
      "http://localhost:8000/api/rooms/r1/messages",
    );
  });
});

describe("送る本文", () => {
  function sentBody(spy: ReturnType<typeof stubFetch>): unknown {
    return JSON.parse(lastCall(spy).init.body as string);
  }

  // キー名はバックエンドのスキーマと合わせる必要がある、唯一の手書きの契約。
  // ずれると 422 になる
  test("signUp は login_name と display_name を送る", async () => {
    const spy = stubFetch(jsonResponse({ public_id: "u1" }));

    await signUp("alice", "アリス");

    expect(sentBody(spy)).toEqual({
      login_name: "alice",
      display_name: "アリス",
    });
  });

  test("signUp は display_name を省略できる", async () => {
    const spy = stubFetch(jsonResponse({ public_id: "u1" }));

    await signUp("alice");

    // 空文字を送るとバックエンドの min_length=1 に弾かれる
    expect(sentBody(spy)).toEqual({ login_name: "alice" });
  });

  test("logIn は login_name を送る", async () => {
    const spy = stubFetch(jsonResponse({ public_id: "u1" }));

    await logIn("alice");

    expect(sentBody(spy)).toEqual({ login_name: "alice" });
  });

  test("sendMessage は client_message_id と body を送る", async () => {
    const spy = stubFetch(jsonResponse({ id: 1 }));

    await sendMessage("r1", "c1", "やあ");

    expect(sentBody(spy)).toEqual({ client_message_id: "c1", body: "やあ" });
  });
});

describe("応答の扱い", () => {
  test("失敗は ApiError になり、状態で分岐できる", async () => {
    stubFetch(jsonResponse({ detail: "この名前は既に使われています" }, 409));

    const error = await signUp("alice").catch((error: unknown) => error);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).message).toBe("この名前は既に使われています");
  });

  test("本文が JSON でなくても投げ切る", async () => {
    stubFetch(
      new Response("<html>502</html>", {
        status: 502,
        statusText: "Bad Gateway",
      }),
    );

    const error = await signUp("alice").catch((error: unknown) => error);

    expect((error as ApiError).status).toBe(502);
    expect((error as ApiError).message).toContain("502");
  });

  test("一覧はそのまま返す", async () => {
    const message = {
      id: 1,
      client_message_id: "c1",
      body: "やあ",
      created_at: "2026-08-30T04:42:48.538588+00:00",
      sender: { public_id: "u1", display_name: "アリス" },
    };
    stubFetch(jsonResponse([message]));

    await expect(fetchMessages("r1")).resolves.toEqual([message]);
  });

  test("204 は本文を読まずに終わる", async () => {
    stubFetch(new Response(null, { status: 204 }));

    await expect(logOut()).resolves.toBeUndefined();
  });
});

describe("WebSocket の URL", () => {
  test("http は ws になる", () => {
    expect(messageStreamUrl("r1")).toBe(
      "ws://localhost:8000/api/rooms/r1/messages/stream",
    );
  });
});
