/**
 * 吹き出しに添える時刻。
 *
 * 時刻の表す瞬間は同じでも、書き方は読み手の設定で変わる。画面は日本語で
 * 統一してあるので、書式も `ja-JP` に寄せて 24 時間表記にする。
 * 何時に見えるかは、見ている人の地域のまま。
 */
export function formatTime(createdAt: string): string {
  return new Date(createdAt).toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
