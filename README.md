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
