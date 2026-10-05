#!/usr/bin/env python3
"""直近のClaude Codeセッションの最終応答を取り出してyomiyasu_lintにかける。

yomiyasuプラグインがインストールされていることが前提（パスは scripts/yomiyasu_lint_path.py で解決する）。

使い方:
  scripts/lint-last-response.py            # カレントディレクトリに対応するプロジェクトの最新セッション
  scripts/lint-last-response.py -n 3       # 直近3応答をまとめて検査
  scripts/lint-last-response.py --json     # JSONで出力
セッションログは ~/.claude/projects/<エンコード済みcwd>/<session>.jsonl にある。
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yomiyasu_lint_path import INSTALL_HINT, resolve  # noqa: E402


def project_dir(cwd: Path) -> Path:
    encoded = str(cwd).replace("/", "-")
    return Path.home() / ".claude" / "projects" / encoded


def assistant_texts(jsonl: Path, min_len: int = 1):
    out = []
    for line in jsonl.open(encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") != "assistant":
            continue
        for c in d.get("message", {}).get("content", []):
            if isinstance(c, dict) and c.get("type") == "text" and len(c["text"]) >= min_len:
                out.append(c["text"])
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, default=1, help="直近n応答を検査（既定1）")
    p.add_argument("--cwd", default=os.getcwd(), help="対象プロジェクトのディレクトリ")
    p.add_argument("--min-len", type=int, default=200, help="この文字数未満の応答は無視")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    a = p.parse_args()

    pdir = project_dir(Path(a.cwd).resolve())
    logs = sorted(pdir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not logs:
        sys.exit(f"セッションログが見つかりません: {pdir}")
    texts = assistant_texts(logs[0], a.min_len)
    if not texts:
        sys.exit(f"{a.min_len}字以上の応答がありません: {logs[0].name}")
    body = "\n\n---\n\n".join(texts[-a.n:])

    lint = resolve()
    if lint is None:
        sys.exit(INSTALL_HINT)
    cmd = [sys.executable, str(lint)]
    if a.json:
        cmd.append("--json")
    if a.strict:
        cmd.append("--strict")
    r = subprocess.run(cmd, input=body, text=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
