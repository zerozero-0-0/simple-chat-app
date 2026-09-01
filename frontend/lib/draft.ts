/** 送信中の下書き。`id` はサーバーに渡す `client_message_id`。 */
export type Draft = {
  id: string;
  body: string;
};

/**
 * 本文に対応する下書きを返す。
 *
 * 同じ本文の送り直しには同じ id を使う。届いていたのに応答を取りこぼした
 * ときも、サーバーが一意制約で 1 通にまとめてくれる。
 * 本文を書き換えてから送ると別の発言なので、id を採り直す。
 */
export function draftFor(current: Draft | null, body: string): Draft {
  return current !== null && current.body === body
    ? current
    : { id: crypto.randomUUID(), body };
}
