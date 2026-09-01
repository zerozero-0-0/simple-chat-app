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
