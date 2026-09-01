import type { Message } from "./types";

/**
 * 受け取ったメッセージを一覧に混ぜる。
 *
 * つなぎ直したときの取り直しと WebSocket から同じものが二度届くので、
 * id で 1 通にまとめる。並びは id の昇順。
 */
export function mergeMessages(
  current: Message[],
  incoming: Message[],
): Message[] {
  const byId = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) {
    byId.set(message.id, message);
  }
  return [...byId.values()].sort((left, right) => left.id - right.id);
}

/**
 * 末尾に自分の発言が新しく増えたか。
 *
 * 増えたときだけ見たいので、末尾の id が前回から変わったことも見る。
 * `mergeMessages` は 1 通も増えていなくても新しい配列を返すため、
 * 末尾が誰かだけで決めると、つなぎ直しの取り直しでも真になる。
 */
export function isMyNewMessage(
  messages: Message[],
  lastSeenId: number | undefined,
  myPublicId: string,
): boolean {
  const last = messages.at(-1);
  return (
    last !== undefined &&
    last.id !== lastSeenId &&
    last.sender.public_id === myPublicId
  );
}
