#!/usr/bin/env python3
"""Stop hookが書いたlint-log.jsonlを集計する。

使い方:
  scripts/lint-log-summary.py                     # 既定のログ（データ置き場のlint-log.jsonl）
  scripts/lint-log-summary.py --split 2026-10-12  # この日付（0時）の前後に分けて比べる。導入前の基準値との比較に使う
  scripts/lint-log-summary.py --by-version        # yomiyasuのバージョンごとに分けて集計する
  scripts/lint-log-summary.py --log path.jsonl --top 15

yomiyasuの更新で検査ルールが変わると同じ文章でも点が変わるので、バージョンをまたいだ点数は比べない。
各行のlint_version（0.2.3以降のStop hookが記録する）で分ける。無い行は「不明」にまとめる。
"""
import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yomiyasu_lint_path import data_dir  # noqa: E402


def load(path: Path) -> list:
    rows = []
    for line in path.open(encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def report(label: str, rows: list, top: int) -> None:
    print(f"[{label}] 応答 {len(rows)} 件")
    if not rows:
        return
    scores = [r.get("score", 0) for r in rows]
    clean = sum(1 for r in rows if not r.get("rules"))
    print(f"  平均 {statistics.mean(scores):.1f} 点 / 中央値 {statistics.median(scores):.0f} 点 / 指摘なし {clean} 件 ({clean / len(rows):.0%})")
    versions = Counter(version_of(r) for r in rows)
    if len(versions) > 1 or "不明" not in versions:
        print("  yomiyasu: " + " / ".join(f"{v} ×{n}" for v, n in versions.most_common()))
    counter = Counter(x for r in rows for x in r.get("rules", []))
    for rule, n in counter.most_common(top):
        print(f"  {n:4d}  {rule}")


def version_of(row: dict) -> str:
    return str(row.get("lint_version") or "不明")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", default=str(data_dir() / "lint-log.jsonl"))
    p.add_argument("--split", help="YYYY-MM-DD。この日付の前後に分けて集計する")
    p.add_argument("--by-version", action="store_true", help="yomiyasuのバージョンごとに分けて集計する")
    p.add_argument("--top", type=int, default=10)
    a = p.parse_args()

    path = Path(a.log)
    if not path.is_file():
        sys.exit(f"ログがありません: {path}")
    rows = load(path)
    if a.by_version:
        groups = {}
        for r in rows:
            groups.setdefault(version_of(r), []).append(r)
        for v in sorted(groups, key=lambda k: (k == "不明", k)):
            report(f"yomiyasu {v}", groups[v], a.top)
        return
    if not a.split:
        report("全期間", rows, a.top)
        return
    cut = time.mktime(time.strptime(a.split, "%Y-%m-%d"))
    report(f"{a.split} より前", [r for r in rows if r.get("ts", 0) < cut], a.top)
    report(f"{a.split} 以降", [r for r in rows if r.get("ts", 0) >= cut], a.top)


if __name__ == "__main__":
    main()
