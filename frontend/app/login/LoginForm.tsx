"use client";

import { NAME_MAX_LENGTH } from "@/lib/types";

type Props = {
  name: string;
  count: number;
  error: string | null;
  pending: boolean;
  canSubmit: boolean;
  onNameChange: (name: string) => void;
  onSubmit: () => void;
};

/** 見た目だけを持つ。状態と通信は `page.tsx` 側にある。 */
export function LoginForm({
  name,
  count,
  error,
  pending,
  canSubmit,
  onNameChange,
  onSubmit,
}: Props) {
  return (
    <form
      className="flex w-full max-w-sm flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium" htmlFor="name">
          ユーザー名
        </label>
        <input
          id="name"
          className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          autoComplete="username"
          autoFocus
          disabled={pending}
        />
        <p className="text-sm text-zinc-500">
          {count} / {NAME_MAX_LENGTH}
        </p>
      </div>

      {error !== null && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <button
        type="submit"
        className="rounded-md bg-zinc-900 px-4 py-2 text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        disabled={!canSubmit}
      >
        {pending ? "入室中..." : "入室する"}
      </button>
    </form>
  );
}
