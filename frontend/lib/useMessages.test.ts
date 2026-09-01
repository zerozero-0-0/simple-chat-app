import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import * as api from "./api";
import type { Message } from "./types";
import { useMessages } from "./useMessages";

function message(id: number, body = `body${id}`): Message {
  return {
    id,
    client_message_id: `c${id}`,
    body,
    created_at: "2026-08-30T04:42:48.538588+00:00",
    sender: { public_id: "u1", display_name: "アリス" },
  };
}

/** 開くたびに記録され、テストから開閉やメッセージ到着を起こせる WebSocket。 */
class FakeSocket {
  static opened: FakeSocket[] = [];

  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.opened.push(this);
  }

  close(): void {
    this.onclose?.();
  }

  static last(): FakeSocket {
    const socket = FakeSocket.opened.at(-1);
    if (socket === undefined) {
      throw new Error("WebSocket が開かれていません");
    }
    return socket;
  }
}

let fetchMessages: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  FakeSocket.opened = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  fetchMessages = vi.spyOn(api, "fetchMessages").mockResolvedValue([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** 接続が開いたことにして、取り直しが終わるまで待つ。 */
async function connect(socket: FakeSocket): Promise<void> {
  await act(async () => {
    socket.onopen?.();
  });
}

/** サーバーから 1 通届いたことにする。 */
async function deliver(socket: FakeSocket, sent: Message): Promise<void> {
  await act(async () => {
    socket.onmessage?.({ data: JSON.stringify(sent) });
  });
}

describe("useMessages", () => {
  test("部屋が決まるまでつながない", () => {
    renderHook(() => useMessages(null));

    expect(FakeSocket.opened).toHaveLength(0);
    expect(fetchMessages).not.toHaveBeenCalled();
  });

  test("つないでから今までの分を取りに行く", async () => {
    fetchMessages.mockResolvedValue([message(1), message(2)]);
    const { result } = renderHook(() => useMessages("r1"));

    // 開く前に取ると、取り終えてから開くまでの間に届いた分が抜ける
    expect(fetchMessages).not.toHaveBeenCalled();

    await connect(FakeSocket.last());

    expect(fetchMessages).toHaveBeenCalledWith("r1", undefined, 100);
    expect(result.current.messages.map((m) => m.id)).toEqual([1, 2]);
    expect(result.current.connected).toBe(true);
  });

  test("届いたメッセージが一覧に増える", async () => {
    const { result } = renderHook(() => useMessages("r1"));
    await connect(FakeSocket.last());

    await deliver(FakeSocket.last(), message(3));

    expect(result.current.messages.map((m) => m.id)).toEqual([3]);
  });

  test("取り直しと WebSocket で重なっても 1 通", async () => {
    const { result } = renderHook(() => useMessages("r1"));
    await connect(FakeSocket.last());
    await deliver(FakeSocket.last(), message(3));

    // 取り直しが同じものを含んで返ってくる
    fetchMessages.mockResolvedValue([message(3), message(4)]);
    FakeSocket.last().close();
    await waitFor(() => expect(FakeSocket.opened).toHaveLength(2));
    await connect(FakeSocket.last());

    expect(result.current.messages.map((m) => m.id)).toEqual([3, 4]);
  });

  test("切れたらつなぎ直し、続きから取り直す", async () => {
    fetchMessages.mockResolvedValue([message(1), message(7)]);
    const { result } = renderHook(() => useMessages("r1"));
    await connect(FakeSocket.last());

    await act(async () => {
      FakeSocket.last().close();
    });
    expect(result.current.connected).toBe(false);

    await waitFor(() => expect(FakeSocket.opened).toHaveLength(2));
    fetchMessages.mockResolvedValue([]);
    await connect(FakeSocket.last());

    // 持っている中でいちばん新しい id から先だけを頼む
    expect(fetchMessages).toHaveBeenLastCalledWith("r1", 7, 100);
  });

  test("1 回で返りきらない取りこぼしは、尽きるまで取り直す", async () => {
    // 満杯で返ってきたら、まだ続きがある
    const full = Array.from({ length: 100 }, (_, index) => message(index + 1));
    fetchMessages
      .mockResolvedValueOnce(full)
      .mockResolvedValueOnce([message(101)]);
    const { result } = renderHook(() => useMessages("r1"));

    await connect(FakeSocket.last());

    expect(fetchMessages).toHaveBeenCalledTimes(2);
    // 2 回目は 1 回目の続きから頼む
    expect(fetchMessages).toHaveBeenLastCalledWith("r1", 100, 100);
    expect(result.current.messages).toHaveLength(101);
  });

  test("取り直しの途中に届いた分でカーソルを飛ばさない", async () => {
    // 11..110 の 100 件。満杯なので、この後に続きがある
    const full = Array.from({ length: 100 }, (_, index) => message(index + 11));
    let release: (received: Message[]) => void = () => {};
    fetchMessages
      .mockImplementationOnce(
        () =>
          new Promise<Message[]>((resolve) => {
            release = resolve;
          }),
      )
      .mockResolvedValue([message(111)]);
    renderHook(() => useMessages("r1"));
    const socket = FakeSocket.last();

    act(() => {
      socket.onopen?.();
    });
    // 1 周目の応答を待っている間に、新しいものが WebSocket で届く
    await deliver(socket, message(161));
    await act(async () => {
      release(full);
    });

    // 続きは届いた 161 からではなく、取ってきた応答の末尾 110 から頼む
    expect(fetchMessages).toHaveBeenLastCalledWith("r1", 110, 100);
  });

  test("取り直しに失敗したら、埋めるべきところから頼み直す", async () => {
    let refuse: (error: Error) => void = () => {};
    fetchMessages
      .mockImplementationOnce(
        () =>
          new Promise<Message[]>((_, reject) => {
            refuse = reject;
          }),
      )
      .mockResolvedValue([]);
    renderHook(() => useMessages("r1"));
    const socket = FakeSocket.last();

    act(() => {
      socket.onopen?.();
    });
    // 取り直しを待つ間に、続きだけが WebSocket で届く
    await deliver(socket, message(50));
    await act(async () => {
      refuse(new Error("取れません"));
    });

    await waitFor(() => expect(FakeSocket.opened).toHaveLength(2));
    await connect(FakeSocket.last());

    // 届いた 50 の先ではなく、まだ 1 件も取れていないところから
    expect(fetchMessages).toHaveBeenLastCalledWith("r1", undefined, 100);
  });

  test("取り直せなければつなぎ直しに回す", async () => {
    fetchMessages.mockRejectedValue(new Error("取れません"));
    renderHook(() => useMessages("r1"));

    await connect(FakeSocket.last());

    await waitFor(() => expect(FakeSocket.opened).toHaveLength(2));
  });

  test("取り直しに続けて失敗すると、つなぎ直す間隔が伸びる", async () => {
    // 取れない状態が続く間、毎回 500ms で叩き直さないこと
    fetchMessages.mockRejectedValue(new Error("取れません"));
    renderHook(() => useMessages("r1"));

    await connect(FakeSocket.last());
    await waitFor(() => expect(FakeSocket.opened).toHaveLength(2), {
      timeout: 1500,
    });

    await connect(FakeSocket.last());
    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(FakeSocket.opened).toHaveLength(2);

    await waitFor(() => expect(FakeSocket.opened).toHaveLength(3), {
      timeout: 1500,
    });
  });

  test("画面を離れたらつなぎ直さない", async () => {
    const { unmount } = renderHook(() => useMessages("r1"));
    await connect(FakeSocket.last());

    unmount();

    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(FakeSocket.opened).toHaveLength(1);
  });

  test("add で自分の送信を先に反映できる", async () => {
    const { result } = renderHook(() => useMessages("r1"));
    await connect(FakeSocket.last());

    act(() => {
      result.current.add(message(5));
    });

    expect(result.current.messages.map((m) => m.id)).toEqual([5]);
  });
});
