"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { enter } from "@/lib/auth";
import { cleanName, countCharacters } from "@/lib/text";
import { NAME_MAX_LENGTH } from "@/lib/types";
import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  // サーバーと同じ手順で整えてから数える。分解形でずれないように
  const cleaned = cleanName(name);
  const count = countCharacters(cleaned);
  const canSubmit = !pending && count > 0 && count <= NAME_MAX_LENGTH;

  async function submit(): Promise<void> {
    setPending(true);
    setError(null);
    try {
      await enter(cleaned);
      router.replace("/");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "入室できませんでした",
      );
      setPending(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <h1 className="text-xl font-semibold">チャットに入る</h1>
        <LoginForm
          name={name}
          count={count}
          error={error}
          pending={pending}
          canSubmit={canSubmit}
          onNameChange={setName}
          onSubmit={() => void submit()}
        />
      </div>
    </main>
  );
}
