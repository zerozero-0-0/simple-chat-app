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
| `APP_ENVIRONMENT` | `development` | `production` にするとセッション Cookie が `Secure` になる |
| `APP_DATABASE_URL` | `backend/chat.db` | 接続先 |
| `APP_CORS_ORIGINS` | `["http://localhost:3000"]` | 許可するオリジン |
| `APP_SESSION_TTL_HOURS` | `336` (14 日) | セッションの有効期限 |

本番は `APP_ENVIRONMENT=production` を設定してください。TLS はリバースプロキシ側で
終端する前提で、uvicorn は平文で受けます。

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
