"use client";

import { useLayoutEffect, useRef } from "react";
import { isMyNewMessage } from "@/lib/messages";
import { formatTime } from "@/lib/time";
import type { Message } from "@/lib/types";

/** 下端からこれだけの範囲を見ているなら、新着を追いかける。 */
const FOLLOW_THRESHOLD_PX = 48;

type Props = {
  messages: Message[];
  /** この人の発言を自分のものとして右に寄せる。 */
  myPublicId: string;
};

/** 見た目だけを持つ。受信と状態は `page.tsx` 側にある。 */
export function MessageList({ messages, myPublicId }: Props) {
  const view = useRef<HTMLDivElement>(null);
  // 読み返している間は追いかけないよう、直前に見ていた位置を覚えておく
  const following = useRef(true);
  // 再描画と新着を見分けるための、直前の末尾
  const lastSeen = useRef<number | undefined>(undefined);

  // ペイント前に動かす。伸びた直後の位置が一瞬でも見えると、その間に来た
  // scroll イベントを「下端から離れた」と読み違える
  useLayoutEffect(() => {
    const element = view.current;
    if (element === null) {
      return;
    }
    // 自分が送ったものは、読み返している最中でも見えるところへ連れていく
    if (isMyNewMessage(messages, lastSeen.current, myPublicId)) {
      following.current = true;
    }
    lastSeen.current = messages.at(-1)?.id;
    if (following.current) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, myPublicId]);

  return (
    <div
      ref={view}
      // 読み上げでも新着が分かるように、更新され続ける領域として印を付ける
      role="log"
      aria-label="発言の一覧"
      className="flex flex-1 flex-col overflow-y-auto p-4"
      onScroll={(event) => {
        const { scrollTop, scrollHeight, clientHeight } = event.currentTarget;
        following.current =
          scrollHeight - scrollTop - clientHeight <= FOLLOW_THRESHOLD_PX;
      }}
    >
      {messages.length === 0 ? (
        <p className="m-auto text-sm text-zinc-500">まだ発言はありません</p>
      ) : (
        // 少ないうちは下に寄せる。溢れたら auto は 0 になり、上まで辿れる
        <ol className="mt-auto flex flex-col gap-3">
          {messages.map((message) => {
            const mine = message.sender.public_id === myPublicId;
            const time = (
              <time
                className="text-xs text-zinc-500"
                dateTime={message.created_at}
              >
                {formatTime(message.created_at)}
              </time>
            );
            return (
              <li
                key={message.id}
                className={`flex flex-col gap-1 ${mine ? "items-end" : "items-start"}`}
              >
                {!mine && (
                  <span className="px-1 text-xs text-zinc-500">
                    {message.sender.display_name}
                  </span>
                )}
                <div className="flex max-w-[75%] items-end gap-1">
                  {mine && time}
                  <p
                    className={`whitespace-pre-wrap break-words rounded-2xl px-3 py-2 ${
                      mine
                        ? "bg-emerald-500 text-white"
                        : "bg-zinc-200 dark:bg-zinc-800"
                    }`}
                  >
                    {message.body}
                  </p>
                  {!mine && time}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
