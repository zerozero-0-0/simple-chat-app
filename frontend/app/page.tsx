"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchMe, logOut } from "@/lib/api";
import type { User } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => router.replace("/login"));
  }, [router]);

  if (user === null) {
    return <main className="flex flex-1 items-center justify-center p-6" />;
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 p-6">
      <p>
        <span className="font-semibold">{user.display_name}</span> として入室中
      </p>
      <button
        type="button"
        className="rounded-md border border-zinc-300 px-4 py-2 dark:border-zinc-700"
        onClick={() => {
          setError(null);
          void logOut()
            .then(() => router.replace("/login"))
            .catch(() => setError("退出できませんでした"));
        }}
      >
        退出する
      </button>
      {error !== null && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </main>
  );
}
