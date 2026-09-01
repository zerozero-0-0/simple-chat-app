"use client";

import type { Room, User } from "@/lib/types";

type Props = {
  room: Room;
  user: User;
  connected: boolean;
  onLogOut: () => void;
};

/** 見た目だけを持つ。状態は `page.tsx` 側にある。 */
export function RoomHeader({ room, user, connected, onLogOut }: Props) {
  return (
    <header className="flex items-center gap-3 border-b border-zinc-200 p-4 dark:border-zinc-800">
      <h1 className="font-semibold">{room.name}</h1>
      {!connected && (
        <span className="text-sm text-zinc-500" role="status">
          つなぎ直しています
        </span>
      )}
      <span className="ml-auto text-sm text-zinc-500">{user.display_name}</span>
      <button
        type="button"
        className="rounded-md border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-700"
        onClick={onLogOut}
      >
        退出する
      </button>
    </header>
  );
}
