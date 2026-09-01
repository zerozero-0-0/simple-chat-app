/** 吹き出しに添える時刻。見ている人の地域の時と分で出す。 */
export function formatTime(createdAt: string): string {
  return new Date(createdAt).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}
