#!/usr/bin/env python3
"""インストール済みのyomiyasuプラグインからyomiyasu_lint.pyの場所を解決する。

探索順:
  1. 環境変数YOMIYASU_LINT（ファイルパスを直接指定）
  2. ~/.claude/plugins/installed_plugins.json のyomiyasuのinstallPath
  3. ~/.claude/plugins/cache/yomiyasu/yomiyasu/<version>/ のうち最新バージョン
  4. npx skills / openskillsでの配置先（~/.claude/skills, ~/.agents/skills）
  5. データ置き場に置いたコピー（<data_dir>/yomiyasu_lint.py と markdown_visibility.py の2ファイル。
     yomiyasuを入れない運用向け。yomiyasu 1.0.8以降のyomiyasu_lint.pyは同じディレクトリの
     markdown_visibility.pyを読み込むので、1ファイルだけでは動かない）
見つからなければ終了コード3で、インストール方法を案内する。

lint_version(path) は、そのyomiyasu_lint.pyが属するyomiyasuのバージョンを返す
（.claude-plugin/plugin.json のversion。無ければファイル内容のsha1先頭8桁）。Stop hookが記録に残す。

データ置き場（data_dir()）は、プラグインとして動いているときはCLAUDE_PLUGIN_DATA
（~/.claude/plugins/data/<id>/。プラグイン更新後も残る）、それ以外は ~/.claude/yomiyasu-chat/。
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

INSTALL_HINT = (
    "yomiyasu_lint.pyが見つかりません。yomiyasuプラグインをインストールしてください。\n"
    "  /plugin marketplace add nanaism/yomiyasu\n"
    "  /plugin install yomiyasu@yomiyasu\n"
    "別の場所にある場合は環境変数YOMIYASU_LINTでパスを指定できます。\n"
    "yomiyasuを入れない場合は、データ置き場にyomiyasu_lint.pyとmarkdown_visibility.pyのコピー（MIT）を\n"
    "2ファイルそろえて置いても動きます。"
)


def data_dir() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(env) if env else Path.home() / ".claude" / "yomiyasu-chat"


def _version_key(p: Path):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.\-]", p.name)]


def resolve() -> Path | None:
    env = os.environ.get("YOMIYASU_LINT")
    if env and Path(env).is_file():
        return Path(env)

    home = Path.home()
    rel = Path("scripts/yomiyasu_lint.py")

    reg = home / ".claude/plugins/installed_plugins.json"
    if reg.is_file():
        try:
            plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
            for key, entries in plugins.items():
                if key.split("@")[0] != "yomiyasu":
                    continue
                for e in entries:
                    cand = Path(e.get("installPath", "")) / rel
                    if cand.is_file():
                        return cand
        except (json.JSONDecodeError, OSError):
            pass

    cache = home / ".claude/plugins/cache/yomiyasu/yomiyasu"
    if cache.is_dir():
        for v in sorted(cache.iterdir(), key=_version_key, reverse=True):
            if (v / rel).is_file():
                return v / rel

    for base in (home / ".claude/skills/yomiyasu", home / ".agents/skills/yomiyasu"):
        if (base / rel).is_file():
            return base / rel

    vendored = data_dir() / "yomiyasu_lint.py"
    if vendored.is_file() and (vendored.parent / "markdown_visibility.py").is_file():
        return vendored
    return None


def lint_version(lint: Path) -> str:
    """yomiyasu_lint.pyが属するyomiyasuのバージョン。plugin.jsonが無ければ内容のsha1先頭8桁。"""
    for base in (lint.parent.parent, lint.parent):
        manifest = base / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            try:
                v = json.loads(manifest.read_text(encoding="utf-8")).get("version")
                if v:
                    return str(v)
            except (json.JSONDecodeError, OSError):
                pass
    try:
        return "sha1:" + hashlib.sha1(lint.read_bytes()).hexdigest()[:8]
    except OSError:
        return "unknown"


if __name__ == "__main__":
    p = resolve()
    if p is None:
        print(INSTALL_HINT, file=sys.stderr)
        sys.exit(3)
    print(p)
