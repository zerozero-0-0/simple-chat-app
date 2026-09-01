"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMessages, messageStreamUrl } from "./api";
import { mergeMessages } from "./messages";
import type { Message } from "./types";

/** つなぎ直すまでの待ち時間。続けて失敗するほど長く待つ。 */
const RETRY_DELAYS_MS = [500, 1000, 2000, 5000];

/** 取り直し 1 回あたりの件数。サーバーが認める上限。 */
const CATCH_UP_LIMIT = 100;

export type MessageStream = {
  messages: Message[];
  connected: boolean;
  /** 自分で送ったメッセージを一覧に足す。 */
  add: (message: Message) => void;
};

/**
 * 部屋のメッセージを受け取り続ける。
 *
 * つないでから取り直す順にしてあるので、初回もつなぎ直しも同じ道を通る。
 * 取っている間に届いた分は WebSocket からも来て、id で 1 通にまとまる。
 *
 * 1 つの部屋を見続ける前提で持つ。別の部屋に移るときは、使う側を
 * `key` で作り直して一覧ごと入れ替える。
 */
export function useMessages(publicId: string | null): MessageStream {
  const [messages, setMessages] = useState<Message[]>([]);
  const [connected, setConnected] = useState(false);
  const known = useRef<Message[]>([]);
  // 取り直しで埋めた末尾。WebSocket が先に運んできた分では進めない。
  // 進めてしまうと、その手前の取りこぼしを二度と頼まなくなる
  const filled = useRef<number | undefined>(undefined);

  const receive = useCallback((incoming: Message[]) => {
    known.current = mergeMessages(known.current, incoming);
    setMessages(known.current);
  }, []);

  const add = useCallback((message: Message) => receive([message]), [receive]);

  useEffect(() => {
    if (publicId === null) {
      return;
    }
    const room = publicId;

    let stopped = false;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let socket: WebSocket | undefined;

    function open(): void {
      const opened = new WebSocket(messageStreamUrl(room));
      socket = opened;

      opened.onopen = () => {
        setConnected(true);
        catchUp(opened);
      };

      opened.onmessage = (event) => {
        receive([JSON.parse(event.data as string) as Message]);
      };

      opened.onclose = () => {
        setConnected(false);
        retry();
      };
    }

    /**
     * つないだ時点までの分を取る。初回は一覧ごと、以降は続きだけ。
     *
     * 1 回で返るのは `CATCH_UP_LIMIT` 件までなので、それだけ返ってきた
     * 間はカーソルを進めて続きを取る。長く切れていても一覧が繋がる。
     */
    async function fill(): Promise<void> {
      for (;;) {
        const received = await fetchMessages(
          room,
          filled.current,
          CATCH_UP_LIMIT,
        );
        if (stopped) {
          return;
        }
        receive(received);

        const last = received.at(-1);
        if (last === undefined) {
          return;
        }
        filled.current = last.id;
        if (received.length < CATCH_UP_LIMIT) {
          return;
        }
      }
    }

    function catchUp(opened: WebSocket): void {
      fill()
        .then(() => {
          // 追いつけたところで、待ち時間を最初に戻す
          failures = 0;
        })
        .catch(() => {
          // 取り直せなかったので、つなぎ直しに任せる
          opened.close();
        });
    }

    function retry(): void {
      if (stopped) {
        return;
      }
      const delay =
        RETRY_DELAYS_MS[Math.min(failures, RETRY_DELAYS_MS.length - 1)];
      failures += 1;
      timer = setTimeout(open, delay);
    }

    open();

    return () => {
      stopped = true;
      clearTimeout(timer);
      if (socket !== undefined) {
        // つなぎ直しの経路を外してから閉じる
        socket.onclose = null;
        socket.close();
      }
      setConnected(false);
    };
  }, [publicId, receive]);

  return { messages, connected, add };
}
