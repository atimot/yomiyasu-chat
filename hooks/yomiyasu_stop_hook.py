#!/usr/bin/env python3
"""Claude CodeのStop hook。最終応答をyomiyasu_lintと個人パターンで検査し、結果を通知する。

環境変数:
  YOMIYASU_HOOK_MODE       warn (既定) | block | off
                           warn:  スコアと指摘を警告として表示するだけ
                           block: スコアが閾値未満なら1回だけ書き直しを求める（2回目以降はwarnと同じ）
  YOMIYASU_HOOK_THRESHOLD  blockの閾値（既定90）
  YOMIYASU_HOOK_MIN_LEN    この文字数未満の応答は検査しない（既定200）
  YOMIYASU_HOOK_IGNORE     無視するルール名（カンマ区切り。例: sentence_end_repetition）
  YOMIYASU_HOOK_LOG        検査結果を追記するJSONL（既定は<データ置き場>/lint-log.jsonl、空文字で無効）
  YOMIYASU_LINT            yomiyasu_lint.pyのパスを直接指定（省略時はインストール済みのyomiyasuから解決）

データ置き場は、プラグインとして入れた場合はCLAUDE_PLUGIN_DATA（~/.claude/plugins/data/<id>/）、
それ以外は ~/.claude/yomiyasu-chat/。個人パターンのpatterns.tsv（正規表現<TAB>説明）もここに置くと、
yomiyasuの指摘に重ねて検出する。

点数はyomiyasu_lintと同じ式（100点からwarn/errorは5点、infoは2点減点）で、
無視ルールを除き個人パターンを足したうえで計算し直す。
記録には使ったyomiyasuのバージョン（lint_version）も残す。yomiyasuの更新で検査ルールが変わると
同じ文章でも点が変わるので、集計はバージョンごとに分けて見る（lint-log-summary.py --by-version）。
yomiyasuが未インストール、または検査中に失敗した場合は何もせず終了する（フェイルオープン）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from yomiyasu_lint_path import data_dir, lint_version, resolve  # noqa: E402

MARKER = re.compile(r"^\s*\[yomiyasu\]\s*$", re.M)
JAPANESE = re.compile(r"[぀-ヿ一-鿿]")
STATE_DIR = Path(tempfile.gettempdir()) / "yomiyasu-chat-hook"


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def already_blocked(session_id: str, prompt_id: str) -> bool:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    f = STATE_DIR / f"{session_id}-{prompt_id}"
    if f.exists():
        return True
    f.write_text(str(time.time()))
    return False


def load_patterns(path: Path) -> list:
    """patterns.tsvを読む。1行 = 正規表現<TAB>説明。空行と # 始まりは無視。コンパイルできない正規表現は飛ばす。"""
    out = []
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        pat, _, desc = raw.partition("\t")
        try:
            out.append((re.compile(pat.strip()), desc.strip() or pat.strip()))
        except re.error:
            continue
    return out


def personal_findings(text: str, patterns: list) -> list:
    """コードブロックとインラインコードを除いた各行に個人パターンを当てる。"""
    out = []
    in_code = False
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        scan = re.sub(r"`[^`]+`", "", line)
        for rx, desc in patterns:
            for m in rx.finditer(scan):
                out.append({
                    "rule": "personal",
                    "line": line_no,
                    "severity": "warn",
                    "message": desc,
                    "snippet": m.group(0),
                })
    return out


def rescore(findings: list) -> int:
    penalty = sum(5 if f.get("severity") in ("warn", "error") else 2 for f in findings)
    return max(0, 100 - penalty)


def summarize(findings: list, limit: int = 3) -> str:
    lines = []
    for f in findings[:limit]:
        snippet = (f.get("snippet") or "").strip()
        if len(snippet) > 40:
            snippet = snippet[:40] + "…"
        lines.append(f"- [{f.get('severity', '').upper()}] {f.get('rule')}: {snippet}")
    rest = len(findings) - limit
    if rest > 0:
        lines.append(f"- ほか{rest}件")
    return "\n".join(lines)


def append_log(log_path: str, data: dict, text: str, score: int, findings: list,
               version: str) -> None:
    if not log_path:
        return
    try:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps({
                "ts": int(time.time()),
                "session_id": data.get("session_id"),
                "cwd": data.get("cwd"),
                "chars": len(text),
                "score": score,
                "rules": [f.get("rule") for f in findings],
                "lint_version": version,
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main() -> None:
    mode = os.environ.get("YOMIYASU_HOOK_MODE", "warn").lower()
    if mode == "off":
        return
    threshold = int(os.environ.get("YOMIYASU_HOOK_THRESHOLD", "90"))
    min_len = int(os.environ.get("YOMIYASU_HOOK_MIN_LEN", "200"))
    ignore = {s.strip() for s in os.environ.get("YOMIYASU_HOOK_IGNORE", "").split(",") if s.strip()}
    ddir = data_dir()
    log_path = os.environ.get("YOMIYASU_HOOK_LOG", str(ddir / "lint-log.jsonl"))

    data = json.load(sys.stdin)
    text = MARKER.sub("", data.get("last_assistant_message") or "").strip()
    if len(text) < min_len or not JAPANESE.search(text):
        return

    lint = resolve()
    if lint is None:
        return
    r = subprocess.run([sys.executable, str(lint), "--json"], input=text, text=True,
                       capture_output=True, timeout=20)
    if r.returncode not in (0, 1) or not r.stdout.strip():
        return
    result = json.loads(r.stdout)
    findings = [f for f in result.get("findings", []) if f.get("rule") not in ignore]
    findings += personal_findings(text, load_patterns(ddir / "patterns.tsv"))
    score = rescore(findings)

    append_log(log_path, data, text, score, findings, lint_version(lint))

    if not findings:
        return

    head = f"yomiyasu_lint: {score}/100（{len(findings)}件）"

    if mode == "block" and score < threshold and not already_blocked(
            str(data.get("session_id")), str(data.get("prompt_id"))):
        detail = "\n".join(
            f"- L{f.get('line')} {f.get('rule')}: {f.get('message')}\n  > {f.get('snippet')}"
            for f in findings)
        emit({
            "decision": "block",
            "reason": (f"{head}。閾値{threshold}未満のため、直前の応答を次の指摘に沿って書き直してください。"
                       f"意味は変えず、文体だけを直してください。\n{detail}"),
        })
        return

    emit({"systemMessage": f"{head}\n{summarize(findings)}"})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # フェイルオープン
        print(f"yomiyasu_stop_hook: {e}", file=sys.stderr)
    sys.exit(0)
