"use client";

import { MESSAGE_BODY_MAX_LENGTH } from "@/lib/types";

type Props = {
  body: string;
  count: number;
  tooLong: boolean;
  canSend: boolean;
  error: string | null;
  onBodyChange: (body: string) => void;
  onSubmit: () => void;
};

/** 見た目だけを持つ。送信と状態は `page.tsx` 側にある。 */
export function MessageForm({
  body,
  count,
  tooLong,
  canSend,
  error,
  onBodyChange,
  onSubmit,
}: Props) {
  return (
    <form
      className="flex flex-col gap-2 border-t border-zinc-200 p-4 dark:border-zinc-800"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="flex items-end gap-2">
        <label className="sr-only" htmlFor="body">
          メッセージ
        </label>
        <textarea
          id="body"
          rows={1}
          className="max-h-40 flex-1 resize-none rounded-2xl border border-zinc-300 px-3 py-2 dark:border-zinc-700"
          placeholder="メッセージを入力"
          value={body}
          onChange={(event) => onBodyChange(event.target.value)}
          onKeyDown={(event) => {
            // 変換を確定する Enter と、送信する Enter を分ける
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault();
              onSubmit();
            }
          }}
        />
        <button
          type="submit"
          className="rounded-2xl bg-emerald-500 px-4 py-2 text-white disabled:opacity-50"
          disabled={!canSend}
        >
          送信
        </button>
      </div>

      {tooLong && (
        <p className="text-sm text-red-600" role="alert">
          {count - MESSAGE_BODY_MAX_LENGTH} 文字多いです
        </p>
      )}
      {error !== null && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
