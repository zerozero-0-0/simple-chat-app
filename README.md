# simple-chat-app

LINE風の簡単なチャットアプリ。

## 技術スタック

| 領域 | 使用技術 |
| -- | -- |
| フロントエンド | TypeScript / Next.js / Tailwind CSS |
| バックエンド | Python / FastAPI |
| データベース | SQLite |
| ツール管理 | mise |

バージョンは [`mise.toml`](./mise.toml) で固定しています。

## 環境構築

事前に [mise](https://mise.jdx.dev/) をインストールしてください。

```bash
# mise.toml を信頼して node / pnpm / python / uv / pre-commit を取得
mise trust
mise install

# 依存パッケージをインストール
pnpm --dir frontend install
uv sync --project backend

# コミット時のフォーマット・リントを有効化
pre-commit install
```

## 開発

```bash
# フロントエンド http://localhost:3000
pnpm --dir frontend dev

# バックエンド http://localhost:8000
uv run --project backend uvicorn app.main:app --reload --app-dir backend
```

API ドキュメントは http://localhost:8000/docs で確認できます。

バックエンドの設定は環境変数と `backend/.env` から読みます(接頭辞 `APP_`)。
起動する場所に関わらず `backend/.env` を読むので、リポジトリルートから uvicorn を
起動しても、`--directory backend` で pytest を走らせても同じ設定になります。

| キー | 既定 | 用途 |
| -- | -- | -- |
| `APP_DATABASE_URL` | `sqlite+aiosqlite:///` + `backend/chat.db` の絶対パス | SQLAlchemy の接続 URL |
| `APP_CORS_ORIGINS` | `["http://localhost:3000"]` | 許可するオリジン。JSON 配列で渡す |
| `APP_SESSION_TTL_HOURS` | `336` (14 日) | セッションの猶予 |
| `APP_SESSION_COOKIE_SECURE` | `false` | セッション Cookie の `Secure`。https に移すとき `true` にする |

セッションは使うたびに期限が延びます。残りが猶予の半分を切ったときに延ばすので、
最後に使ってから 7 日〜14 日の間に切れます。

### 将来的なhttps以降手順

いまは http で運用しているため、セッション Cookie に `Secure` は付きません。
https に移すときは次の 3 つを変更します。

1. `APP_SESSION_COOKIE_SECURE=true` を設定する
2. `APP_CORS_ORIGINS` を https のオリジンにする
3. リバースプロキシで TLS を終端し、80 番は 443 へリダイレクトする

`Secure` を付けた Cookie はブラウザが https でしか送らないので、1 だけを先に設定すると
ログインが成立しません。3 つをまとめて切り替えてください。

## テスト

```bash
uv run --directory backend pytest
```

## コード品質

| 対象 | フォーマット | リント | 型チェック |
| -- | -- | -- | -- |
| frontend | Biome | ESLint | — |
| backend | ruff | ruff | ty |

pre-commit がコミット時に上記を実行します。手動で全ファイルにかける場合:

```bash
pre-commit run --all-files
```

同じチェックを GitHub Actions でも実行しています([`.github/workflows`](./.github/workflows))。

## ディレクトリ構成

```
frontend/  Next.js アプリケーション
backend/   FastAPI アプリケーション
```
