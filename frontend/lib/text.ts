/**
 * 入力された文字数を数える。
 *
 * バックエンドの `max_length` は Unicode のコードポイントで数える。
 * `String.length` は UTF-16 単位なので、絵文字があるとサーバーとずれる。
 */
export function countCharacters(value: string): number {
  return [...value].length;
}

/**
 * 名前を整える。バックエンドの `cleaned()` と同じ手順。
 *
 * 数える前に通さないと、分解形で入力された名前をサーバーが受けるのに
 * 画面が上限超過として弾く。
 */
export function cleanName(value: string): string {
  return value.normalize("NFC").trim();
}
