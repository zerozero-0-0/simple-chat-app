## simple-chat-app
LINE風の簡単なチャットアプリ

## 技術スタック
### フロントエンド
- 言語: TypeScript
- パッケージマネージャー: pnpm 10.33.0
- フレームワーク: Next.js

### バックエンド
- パッケージマネージャー: uv
- 言語: Python 3.12
- フレームワーク: FastAPI

### データベース
- SQLite

## 要件
以下の2つの画面を実装し、各画面に次の機能を持たせること

|画面|機能|
|--|--|
|ログイン画面|ユーザー名で入室できる簡易的な認証|
|チャットルーム画面|メッセージ送信フォーム、メッセージ一覧の表示|

## 設計

### ID
`users` と `rooms` は内部 ID と公開 ID を分ける。

|カラム|役割|
|--|--|
|`id`|内部用。FK と索引に使う|
|`public_id`|API と URL に出す不透明な ID|

`users` はさらに `login_name`(一意)と `display_name`(重複可)を持つ。
`messages` は連番の内部 ID をそのまま公開し、`?after=<id>` のカーソルに使う。

### 認証
`sessions` テーブルにセッションを持ち、HttpOnly Cookie で session id を渡す。
`signup` と `login` はエンドポイントを分ける。signup は重複時 409、login は不在時 404。

### メッセージ
送信は REST、受信は WebSocket。
クライアントが `client_message_id` を採番し、`UNIQUE(room_id, client_message_id)` で再送を冪等にする。

### 既読
`room_members.last_read_message_id` の watermark 方式。
既読数は `last_read_message_id >= そのメッセージの id` のメンバー数。

### 構成
```
backend/app/     main.py, config.py, db.py, models.py, schemas.py, deps.py, routers/
backend/tests/
frontend/app/    Next.js App Router
frontend/lib/    API クライアント
```

DB アクセスは SQLAlchemy 2.0 の非同期構成(aiosqlite)。ORM モデルと Pydantic スキーマは分ける。

## 前提
実装は以下の観点に従うこと
- 機能実装: 必要な機能が正しく動作しているか
- コード品質: コードの整理、読みやすさ、適切な分割ができているか
- 設計力: APIやDB設計がシンプルで拡張性があるか

曖昧な部分は、適切だと思われる実装を提案し、承認されたのち実装すること。
各実装は公式docsを参照しベストプラクティスに従うこと