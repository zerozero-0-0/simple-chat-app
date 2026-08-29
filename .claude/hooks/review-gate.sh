#!/usr/bin/env bash
# staged 差分がレビュー済みかを判定するコミットゲート。
#
#   check (既定) : PreToolUse の入力を読み、git commit なら未レビュー時に deny する
#   pass         : いまの staged 差分をレビュー済みとして記録する
#
# レビュー済みの印は「そのとき staged だった差分のハッシュ」。git add で内容が
# 変われば自動的に無効になるので、直した後は必ずレビューし直しになる。
set -uo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
py=$(command -v python3 || echo /usr/bin/python3)

git_dir=$(git rev-parse --absolute-git-dir 2>/dev/null) || exit 0
marker="$git_dir/claude-review-ok"

if [ "${1-check}" = pass ]; then
  git diff --cached | git hash-object --stdin >"$marker"
  echo "staged 差分をレビュー済みとして記録しました"
  exit 0
fi

deny() {
  "$py" -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": sys.argv[1],
}}))' "$1"
  exit 0
}

# commit かどうかと、commit なら index の内容をそのままコミットするかを判定する。
# Bash の呼び出しすべてで走るので、commit でなければ skip がすぐ返る。
verdict=$("$py" "$here/review_gate_parse.py") || {
  echo "コミットゲートの判定に失敗しました: $here/review_gate_parse.py" >&2
  exit 2
}

case "$verdict" in
  skip) exit 0 ;;
  deny*) deny "${verdict#deny$'\t'}" ;;
esac

# stage が空でも例外にはしない。空のまま素通しすると、フックが走る時点では空で
# 後から中身が入る commit を通してしまう。空の差分もレビューを通れば照合で通る
# ので、メッセージだけ直す `--amend` のような commit も塞がらない。
staged=$(git diff --cached | git hash-object --stdin)
[ -f "$marker" ] && [ "$(cat "$marker")" = "$staged" ] && exit 0

deny 'staged 差分がまだレビューされていません。Agent ツールで subagent_type="code-reviewer" に委譲し、独立した視点のレビューを受けてください。指摘が無ければ code-reviewer 自身がゲートを解除するので、その後で commit し直してください。'
