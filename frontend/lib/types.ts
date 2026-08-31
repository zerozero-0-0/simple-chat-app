/** バックエンドが返す形をそのまま写したもの。変換は挟まない。 */

export type User = {
  public_id: string;
  login_name: string;
  display_name: string;
};

export type Room = {
  public_id: string;
  name: string;
};

/** メッセージの送信者。他のユーザーには `login_name` を出さない。 */
export type MessageSender = {
  public_id: string;
  display_name: string;
};

export type Message = {
  id: number;
  client_message_id: string;
  body: string;
  /** オフセット付きの ISO 8601。`new Date()` にそのまま渡せる。 */
  created_at: string;
  sender: MessageSender;
};

/** 入力の上限。バックエンドの `schemas.py` と揃える。 */
export const NAME_MAX_LENGTH = 32;
export const MESSAGE_BODY_MAX_LENGTH = 1000;
