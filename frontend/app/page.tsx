"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  fetchMe,
  fetchRooms,
  joinRoom,
  logOut,
  sendMessage,
} from "@/lib/api";
import { type Draft, draftFor } from "@/lib/draft";
import { countCharacters } from "@/lib/text";
import { MESSAGE_BODY_MAX_LENGTH } from "@/lib/types";
import type { Room, User } from "@/lib/types";
import { useMessages } from "@/lib/useMessages";
import { MessageForm } from "./MessageForm";
import { MessageList } from "./MessageList";
import { RoomHeader } from "./RoomHeader";

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [room, setRoom] = useState<Room | null>(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const { messages, connected, add } = useMessages(room?.public_id ?? null);

  const draft = useRef<Draft | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setUser(await fetchMe());
        const [first] = await fetchRooms();
        if (first === undefined) {
          setError("入れる部屋がありません");
          return;
        }
        setRoom(await joinRoom(first.public_id));
      } catch (caught) {
        // セッションが切れたときだけログイン画面へ。それ以外で戻すと、
        // ログイン画面から入り直してまたここへ、を繰り返す
        if (caught instanceof ApiError && caught.status === 401) {
          router.replace("/login");
          return;
        }
        setError("部屋に入れませんでした");
      }
    })();
  }, [router]);

  const count = countCharacters(body.trim());
  const tooLong = count > MESSAGE_BODY_MAX_LENGTH;
  const canSend = !sending && room !== null && count > 0 && !tooLong;

  async function send(): Promise<void> {
    if (room === null || !canSend) {
      return;
    }
    const typed = body;
    const text = typed.trim();
    draft.current = draftFor(draft.current, text);

    setSending(true);
    setError(null);
    try {
      add(await sendMessage(room.public_id, draft.current.id, text));
      draft.current = null;
      // 応答を待つ間に打ち足した分は残す
      setBody((current) => (current === typed ? "" : current));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "送れませんでした",
      );
    } finally {
      setSending(false);
    }
  }

  function leave(): void {
    setError(null);
    void logOut()
      .then(() => router.replace("/login"))
      .catch(() => setError("退出できませんでした"));
  }

  if (user === null || room === null) {
    return (
      <main className="flex flex-1 items-center justify-center p-6">
        {error !== null && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
      </main>
    );
  }

  return (
    <>
      <RoomHeader
        room={room}
        user={user}
        connected={connected}
        onLogOut={leave}
      />
      <main className="flex flex-1 flex-col overflow-hidden">
        <MessageList messages={messages} myPublicId={user.public_id} />
        <MessageForm
          body={body}
          count={count}
          tooLong={tooLong}
          canSend={canSend}
          error={error}
          onBodyChange={setBody}
          onSubmit={() => void send()}
        />
      </main>
    </>
  );
}
