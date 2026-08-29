"""git commit の引数を読み、index の内容をそのままコミットするかを判定する。

標準入力に PreToolUse の JSON、標準出力に次のいずれかを 1 行で返す。

    skip            コミットを作る呼び出しではない。ゲートは何もしない
    check           index の内容をそのままコミットする。レビュー済みか照合する
    deny<TAB><理由>  index 以外から中身が決まるため、照合しても意味がない

このフックは Bash ツールの呼び出しすべてで走る。settings.json の
`if: "Bash(git commit *)"` で呼び出しを絞ることもできるが、あの足切りは
`git -c core.pager=cat commit` や `/usr/bin/git commit` を取りこぼす
(リテラルの `git commit` で始まらないため)。フックが呼ばれなければここは
走れないので取りこぼしは補えない。したがって足切りは使わず、commit の検出も
このファイルの責務とする。commit でなければ `skip` を返してすぐ終わる。

一方でフックに渡るのは生のコマンド文字列だけで、本体がパースした argv は
渡ってこない。`pnpm test && git commit -m x` から commit の引数を取り出すには、
演算子の分割と字句解析をここで持つしかない。

読み取れない形(`sudo`、制御構文、`timeout` などのラッパ)は commit と判定できず
素通しする。これはうっかりレビューを飛ばすのを防ぐガードレールであって、
回避を防ぐ境界ではない。
"""

import json
import re
import shlex
import sys

# commit するものが index から決まらないオプション。stage した内容と実際に
# コミットされる内容がずれるため、ハッシュの照合が意味を持たなくなる。
UNSTAGED_SOURCE_OPTS = {
    "-a",
    "--all",
    "-i",
    "--include",
    "-o",
    "--only",
    "-p",
    "--patch",
    "--interactive",
    "--pathspec-from-file",
}

# 別のリポジトリ・ワークツリー・index を指す git のグローバルオプションと環境変数。
# ゲートはカレントリポジトリの index しか見ないので、照合が成立しない。
OTHER_REPO_OPTS = {"-C", "--git-dir", "--work-tree"}
OTHER_REPO_ENV = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}

# 値を次のトークンに取る git のグローバルオプション。
GIT_GLOBAL_VALUE_OPTS = OTHER_REPO_OPTS | {
    "-c",
    "--namespace",
    "--exec-path",
    "--config-env",
}

# 値を次のトークンに取る commit のオプション。
COMMIT_VALUE_OPTS_LONG = {
    "--message",
    "--file",
    "--author",
    "--date",
    "--cleanup",
    "--template",
    "--fixup",
    "--squash",
    "--trailer",
    "--reedit-message",
    "--reuse-message",
}
COMMIT_VALUE_OPTS_SHORT = set("mFcCt")

# 値は付けるなら `-Skey` のように連結する形だけのオプション。
COMMIT_OPTIONAL_VALUE_SHORT = set("Su")

COMMIT_FLAGS_LONG = {
    "--verbose",
    "--quiet",
    "--dry-run",
    "--amend",
    "--no-amend",
    "--edit",
    "--no-edit",
    "--verify",
    "--no-verify",
    "--signoff",
    "--no-signoff",
    "--allow-empty",
    "--allow-empty-message",
    "--reset-author",
    "--short",
    "--long",
    "--branch",
    "--no-branch",
    "--status",
    "--no-status",
    "--porcelain",
    "--null",
    "--gpg-sign",
    "--no-gpg-sign",
    "--untracked-files",
    "--progress",
    "--no-progress",
    "--no-post-rewrite",
}
COMMIT_FLAGS_SHORT = set("vqnsez")

OPERATORS = {"&&", "||", ";", ";;", "|", "&", "(", ")", "{", "}"}
REDIRECTS = {"<", ">", ">>", "<<", "<<<", ">&", "&>", "<>", ">|"}

HEREDOC = re.compile(r"<<-?\s*(?:'([^']*)'|\"([^\"]*)\"|([A-Za-z_][A-Za-z0-9_]*))")

# コミットを作らない呼び出し。何を stage したかとは無関係なので、ゲートは通す。
NO_COMMIT_OPTS = {"-h", "--help", "--dry-run"}

# index を書き換えうる git のサブコマンド。同じコマンド列でこれを通してから
# commit すると、フックが見た index と実際にコミットされる内容がずれる。
INDEX_CHANGING_SUBCOMMANDS = {
    "add",
    "am",
    "apply",
    "checkout",
    "cherry-pick",
    "merge",
    "mv",
    "read-tree",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "update-index",
}

ENV_ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=.*", re.DOTALL)


def strip_heredocs(command: str) -> str:
    """ヒアドキュメントの中身を落とす。書かれている内容は実行されないため。"""
    lines = command.split("\n")
    kept: list[str] = []
    i = 0
    while i < len(lines):
        kept.append(lines[i])
        i += 1
        for match in HEREDOC.finditer(kept[-1]):
            terminator = match.group(1) or match.group(2) or match.group(3)
            end = i
            while end < len(lines) and lines[end].strip() != terminator:
                end += 1
            # 終端が見つかったときだけ落とす。見つからないなら `<<` は
            # ヒアドキュメントではなかったので、行はそのまま判定に回す
            if end < len(lines):
                i = end + 1
    return "\n".join(kept)


def splice_continuations(command: str) -> str:
    """行末の `\\` と改行を取り除いて、1 行に繋ぎ直す。"""
    spliced: list[str] = []
    pending = ""
    for line in command.split("\n"):
        backslashes = len(line) - len(line.rstrip("\\"))
        if backslashes % 2 == 1:  # 偶数個なら `\\` のエスケープなので継続ではない
            pending += line[:-1]
        else:
            spliced.append(pending + line)
            pending = ""
    if pending:
        spliced.append(pending)
    return "\n".join(spliced)


def lex(text: str) -> list[str]:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)  # 分解できなければ ValueError


def split_commands(command: str) -> list[list[str]]:
    """コマンド列を、演算子で区切った 1 コマンドずつのトークン列に分解する。"""
    lines = splice_continuations(strip_heredocs(command)).split("\n")
    tokens: list[str] = []
    index = 0
    while index < len(lines):
        chunk = lines[index]
        index += 1
        while True:
            try:
                tokens.extend(lex(chunk))
                break
            except ValueError:
                # 引用符が行内で閉じていない。複数行にまたがる文字列とみなして
                # 次の行を繋ぐ。shell も同じように読むので、繋いで解釈できたなら
                # その解釈が正しい。最後まで閉じなければ解析不能
                if index >= len(lines):
                    raise
                chunk = f"{chunk}\n{lines[index]}"
                index += 1
        tokens.append(";")  # 改行もコマンドの区切り

    commands: list[list[str]] = []
    current: list[str] = []
    position = 0
    while position < len(tokens):
        token = tokens[position]
        if token in OPERATORS:
            commands.append(current)
            current = []
        elif token in REDIRECTS:
            # リダイレクト先はコマンドの引数ではない。直前が `2` のような
            # ファイルディスクリプタなら、それも引数ではないので戻す
            if current and current[-1].isdigit():
                current.pop()
            position += 1
        else:
            current.append(token)
        position += 1
    commands.append(current)
    return [tokens for tokens in commands if tokens]


def git_invocation(tokens: list[str]) -> tuple[str, list[str], str | None] | None:
    """git の呼び出しなら、(サブコマンド, その引数, deny する理由) を返す。

    git の呼び出しでなければ None を返す。理由はここで確定させずに返すだけに
    する。引数を最後まで読むまで、コミットを作る呼び出しかどうかが決まらない。
    """
    blocker: str | None = None
    index = 0

    while index < len(tokens) and (match := ENV_ASSIGNMENT.fullmatch(tokens[index])):
        if match.group(1) in OTHER_REPO_ENV:
            blocker = other_repo_reason(match.group(1))
        index += 1  # 先頭の環境変数の代入

    if index >= len(tokens) or not (
        tokens[index] == "git" or tokens[index].endswith("/git")
    ):
        return None
    index += 1

    while index < len(tokens):
        token = tokens[index]
        name = token.split("=", 1)[0] if token.startswith("--") else token
        if name in OTHER_REPO_OPTS:
            blocker = other_repo_reason(name)
        if token in GIT_GLOBAL_VALUE_OPTS:
            index += 2
        elif token.startswith("-"):
            index += 1
        else:
            break
    else:
        return None

    return tokens[index], tokens[index + 1 :], blocker


def inspect(args: list[str]) -> tuple[str | None, bool]:
    """commit の引数を見て、(deny する理由, コミットを作るか) を返す。

    deny すべき引数を見つけても、最後まで読んでから返す。`--dry-run` が後ろに
    付いていればコミットは作られず、deny する理由が無くなるため。
    """
    reason: str | None = None
    index = 0
    only_pathspecs = False

    while index < len(args):
        arg = args[index]

        if only_pathspecs or not arg.startswith("-") or arg == "-":
            reason = reason or pathspec_reason()
            index += 1
            continue
        if arg == "--":
            only_pathspecs = True
            index += 1
            continue

        if arg.startswith("--"):
            name, _, attached = arg.partition("=")
            if name in NO_COMMIT_OPTS:
                return None, False
            if name in UNSTAGED_SOURCE_OPTS:
                reason = reason or unstaged_source_reason(name)
            elif name in COMMIT_VALUE_OPTS_LONG:
                index += 1 if attached else 2
                continue
            elif name not in COMMIT_FLAGS_LONG:
                reason = reason or unknown_option_reason(name)
            index += 1
            continue

        bundle_reason, creates_commit, consumed = inspect_short_bundle(arg)
        if not creates_commit:
            return None, False
        reason = reason or bundle_reason
        index += consumed

    return reason, True


def pathspec_reason() -> str:
    return (
        "pathspec を付けた commit は index ではなく working tree の内容を"
        "コミットするため、レビュー済みの差分と一致しません。"
        "git add で stage してから、パス指定無しで commit してください。"
    )


def inspect_short_bundle(arg: str) -> tuple[str | None, bool, int]:
    """`-am` のようにまとめられた短いオプションを 1 文字ずつ見る。

    返すのは (deny する理由, コミットを作るか, 消費するトークン数)。値を取る
    文字がまとまりの末尾なら値は次のトークンにあり、途中なら以降が連結された値。
    `-m"init commit"` は 1 トークン `-minit commit` になるので、末尾の文字だけを
    見て判断すると値の一部を取り違える。
    """
    for position, flag in enumerate(arg[1:], start=1):
        if f"-{flag}" in NO_COMMIT_OPTS:
            return None, False, 1
        if f"-{flag}" in UNSTAGED_SOURCE_OPTS:
            return unstaged_source_reason(f"-{flag}"), True, 1
        if flag in COMMIT_VALUE_OPTS_SHORT:
            attached = position < len(arg) - 1
            return None, True, 1 if attached else 2
        if flag in COMMIT_OPTIONAL_VALUE_SHORT:
            return None, True, 1  # 値は連結されている場合だけ
        if flag not in COMMIT_FLAGS_SHORT:
            return unknown_option_reason(f"-{flag}"), True, 1
    return None, True, 1


def stage_changed_reason(subcommand: str) -> str:
    return (
        f"index を書き換えうるサブコマンド (git {subcommand}) が、同じコマンド列の"
        "commit より前にあります。フックは commit の前に走るため、ここで見た差分と"
        "実際にコミットされる内容がずれます。commit は独立したコマンドとして"
        "実行してください。"
    )


def other_repo_reason(name: str) -> str:
    return (
        f"{name} は別のリポジトリ・ワークツリー・index を指すため、"
        "ゲートがレビュー対象の差分を特定できません。"
    )


def unstaged_source_reason(option: str) -> str:
    return (
        f"{option} を付けた commit は index 以外から中身が決まるため、"
        "レビュー済みの差分と一致しません。"
        "git add で明示的に stage してから commit してください。"
    )


def unknown_option_reason(option: str) -> str:
    return (
        f"ゲートが解釈できない commit のオプション {option} が付いています。"
        "index の内容をそのままコミットする形に書き換えてください。"
    )


def classify(command: str) -> str:
    try:
        commands = split_commands(command)
    except ValueError:
        commands = []  # 分解できなかった。commit を読めなかった扱いにする

    verdict = "skip"  # commit を見つけられなければ、このフックの出番ではない
    stage_changer: str | None = None
    for tokens in commands:
        found = git_invocation(tokens)
        if found is None:
            continue
        subcommand, args, blocker = found

        if subcommand in INDEX_CHANGING_SUBCOMMANDS:
            # 引数まで見れば index を触らないものもあるが、そこは踏み込まず、
            # サブコマンド名だけで安全側に倒す
            stage_changer = stage_changer or subcommand
            continue
        if subcommand != "commit":
            continue

        reason, creates_commit = inspect(args)
        if not creates_commit:
            continue  # コミットを作らないので、何を stage したかとは無関係
        if stage_changer is not None:
            return f"deny\t{stage_changed_reason(stage_changer)}"
        if blocker is not None:
            return f"deny\t{blocker}"
        if reason is not None:
            return f"deny\t{reason}"
        verdict = "check"
    return verdict


def main() -> None:
    try:
        command = json.load(sys.stdin).get("tool_input", {}).get("command", "") or ""
    except (json.JSONDecodeError, AttributeError, ValueError):
        command = ""
    print(classify(command))


if __name__ == "__main__":
    main()
