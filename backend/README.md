# backend

FastAPI + SQLAlchemy 2.0 (非同期) + SQLite。

リポジトリ全体の話は [ルートの README](../README.md) にあります。ここは API と DB の詳細です。

## 起動

```bash
uv sync --project backend
uv run --project backend uvicorn app.main:app --reload --app-dir backend
```

http://localhost:8000/docs に OpenAPI のドキュメントが出ます。

起動時に、テーブルの作成と共通の部屋「みんなの部屋」の用意を済ませます (`main.py` の `lifespan`)。
部屋が 1 つでもあれば作りません。

## API

すべて `/api` の下にあります。セッションが要るのは `/api/auth/me` と `/api/rooms` 配下です。
`signup` と `login` はセッションを発行する入口、`logout` と `health` は Cookie が無くても通ります。

### 認証

| メソッド | パス | 返すもの | 失敗 |
| -- | -- | -- | -- |
| `POST` | `/api/auth/signup` | `201` ユーザー | `409` 名前の重複 / `422` 名前が不正 |
| `POST` | `/api/auth/login` | `200` ユーザー | `404` その名前のユーザーが無い |
| `POST` | `/api/auth/logout` | `204` | — |
| `GET` | `/api/auth/me` | `200` ユーザー | `401` セッションが無い |

`signup` と `login` を分けているので、呼び出し側は状態で分岐できます。フロントは
まず `login` を試し、`404` なら `signup` に回します ([`frontend/lib/auth.ts`](../frontend/lib/auth.ts))。

`logout` はセッションが無くても `204` を返します。何度呼んでも同じ結果になります。

<details>
<summary>リクエストとレスポンスの形</summary>

```jsonc
// POST /api/auth/signup
{ "login_name": "alice", "display_name": "アリス" }  // display_name は省略可

// POST /api/auth/login
{ "login_name": "alice" }

// 200 / 201 のレスポンス。本人にだけ login_name を返す
{ "public_id": "9f2c…", "login_name": "alice", "display_name": "アリス" }
```

</details>

### 部屋

| メソッド | パス | 返すもの | 失敗 |
| -- | -- | -- | -- |
| `GET` | `/api/rooms` | `200` 部屋の配列 | `401` |
| `POST` | `/api/rooms/{public_id}/members` | `200` 部屋 | `401` / `404` その部屋が無い |

入室は何度呼んでも同じ結果になります。二重の参加は `UNIQUE(room_id, user_id)` で弾き、
既に入っていればそのまま `200` を返します。

### メッセージ

| メソッド | パス | 返すもの | 失敗 |
| -- | -- | -- | -- |
| `POST` | `/api/rooms/{public_id}/messages` | `201` メッセージ / 再送は `200` | `401` / `403` 未入室 / `404` / `422` 本文が不正 |
| `GET` | `/api/rooms/{public_id}/messages` | `200` メッセージの配列 | `401` / `403` / `404` |
| `WS` | `/api/rooms/{public_id}/messages/stream` | 新着を流し続ける | ハンドシェイクで拒否 |

**送信は REST、受信は WebSocket** です。送った本人にも WebSocket 経由で戻るので、
配信の経路は 1 本だけです。

`GET` のクエリ:

| キー | 既定 | 意味 |
| -- | -- | -- |
| `after` | なし | この ID より後を古い方から返す。省略すると直近 `limit` 件 |
| `limit` | `50` (最大 `100`) | 返す件数の上限 |

画面を開いたときは `after` 無しで直近を、切断していた間の取りこぼしは
`after=<持っている最後の ID>` で追いかけます。返った件数が `limit` と同じなら
まだ続きがあるので、カーソルを進めて呼び直します。

<details>
<summary>リクエストとレスポンスの形</summary>

```jsonc
// POST /api/rooms/{public_id}/messages
{ "client_message_id": "0d5c…", "body": "やあ" }

// 201 / 200 のレスポンス。WebSocket が流すのも同じ形
{
  "id": 42,
  "client_message_id": "0d5c…",
  "body": "やあ",
  "created_at": "2026-08-30T04:42:48.538588+00:00",
  "sender": { "public_id": "9f2c…", "display_name": "アリス" }
}
```

</details>

### 疎通確認

| メソッド | パス | 返すもの |
| -- | -- | -- |
| `GET` | `/api/health` | `200` `{"status":"ok"}` |

## 設計

### ID を 2 つ持つ

`users` と `rooms` は内部 ID と公開 ID を分けます。

| カラム | 役割 |
| -- | -- |
| `id` | 内部用。FK と索引に使う |
| `public_id` | API と URL に出す不透明な ID (`uuid4().hex`) |

連番をそのまま出すと、URL を書き換えて他人の資源を数え上げられます。

`messages` だけは連番の `id` をそのまま公開します。`?after=<id>` のカーソルに
順序が要るためで、部屋に入っていない人はそもそも一覧を引けません。

### 名前を 2 つ持つ

`users` は `login_name` (一意) と `display_name` (重複可) を分けます。
同姓同名が入室できないと困る一方、認証の鍵は 1 つに定まる必要があります。

どちらも前後の空白を落とし、NFC に揃えてから扱います。macOS の入力やペーストでは
「が」が「か + 濁点」の分解形で届くことがあり、見た目が同じ名前が別のユーザーに
なってしまうためです ([`app/schemas.py`](app/schemas.py) の `cleaned`)。

上限は 32 文字で、Unicode のコードポイントで数えます。フロントも同じ数え方をします。

### セッション

`sessions` テーブルに持ち、HttpOnly Cookie で ID を渡します。

- DB に入るのは SHA-256 のハッシュだけ。DB を読まれても Cookie は作れません
- 使うたびに期限が延びます。残りが半分を切ったときだけ書き戻すので、
  読むだけのリクエストで毎回 DB に書きません
- 期限切れは引いた時点で消します
- 端末ごとに 1 行なので、片方でログアウトしても他方は残ります

`Secure` は設定で切り替えます。https に移すときの手順はルートの README にあります。

### 再送を 2 通にしない

クライアントが `client_message_id` を採番し、`UNIQUE(room_id, sender_id, client_message_id)`
で弾きます。応答を取りこぼして送り直しても 1 通のままです。

**送信者をキーに含めます。** 含めないと、別のユーザーが偶然同じ値を採番したときに
後から送った人のメッセージが消え、しかも他人の本文が `200` で返ります。

一意制約に当たったとき、同じ送信者の同じ `client_message_id` が実在したときだけ
`200` を返します。それ以外の衝突は原因を握りつぶさずそのまま上げます。

### WebSocket の接続管理

接続は部屋ごとと**セッションごと**の両方から引けます ([`app/stream.py`](app/stream.py))。
セッションを見るのは接続時の 1 回だけなので、ログアウトを伝えないと取り消したはずの
セッションにメッセージが流れ続けます。

ハンドシェイクでは Origin も見ます。CORS ミドルウェアは WebSocket を素通しするため、
ここで断らないと HTTP では弾いているオリジンに部屋の中身が流れます。

配信で落ちた接続は捨てて、送信側は止めません。

**既知の制限**: 期限切れは接続中の相手に伝わりません。伝わるのはログアウトだけです。

## 構成

```
app/
  main.py       アプリの組み立て、CORS、起動時のテーブルと部屋の用意
  config.py     設定 (環境変数と backend/.env、接頭辞 APP_)
  db.py         エンジンとセッション
  models.py     ORM のモデル
  schemas.py    リクエストとレスポンスの形 (Pydantic)
  deps.py       セッションの発行と破棄、現在ユーザーの取り出し
  stream.py     WebSocket の接続の台帳
  routers/      auth, rooms, messages, health
tests/
```

ORM のモデルと Pydantic のスキーマは分けています。DB の都合と API に出す形は
別々に変わるためです。

## テスト

```bash
uv run --directory backend pytest
```

WebSocket は同期の `TestClient` で叩きます。`httpx` は WebSocket を扱えず、
`TestClient` は自前のイベントループでアプリを動かすので、[`tests/test_message_stream.py`](tests/test_message_stream.py)
だけファイルの DB を使います。それ以外はテストごとに使い捨てのインメモリ DB です。
