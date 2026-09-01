"use client";

import { useEffect, useRef } from "react";
import { formatTime } from "@/lib/time";
import type { Message } from "@/lib/types";

type Props = {
  messages: Message[];
  /** この人の発言を自分のものとして右に寄せる。 */
  myPublicId: string;
};

/** 見た目だけを持つ。受信と状態は `page.tsx` 側にある。 */
export function MessageList({ messages, myPublicId }: Props) {
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  return (
    <ol className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      {messages.map((message) => {
        const mine = message.sender.public_id === myPublicId;
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
              {mine && (
                <time
                  className="text-xs text-zinc-500"
                  dateTime={message.created_at}
                >
                  {formatTime(message.created_at)}
                </time>
              )}
              <p
                className={`whitespace-pre-wrap break-words rounded-2xl px-3 py-2 ${
                  mine
                    ? "bg-emerald-500 text-white"
                    : "bg-zinc-200 dark:bg-zinc-800"
                }`}
              >
                {message.body}
              </p>
              {!mine && (
                <time
                  className="text-xs text-zinc-500"
                  dateTime={message.created_at}
                >
                  {formatTime(message.created_at)}
                </time>
              )}
            </div>
          </li>
        );
      })}
      <div ref={bottom} />
    </ol>
  );
}
