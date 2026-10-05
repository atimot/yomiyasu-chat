# yomiyasu-chat

Claude Codeの会話応答を、結論ファーストで読みやすい自然な日本語にするoutput styleです。[nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) の文体原則（主述の対応、擬人化と比喩動詞の排除、情報を足さない、太字と箇条書きの抑制など）を、推敲依頼時だけでなく毎回の応答に適用します。

yomiyasu本体は「渡された文章を書き直すスキル」であり、Claude Code自身の会話出力には発火しません。このリポジトリはその隙間を埋めるためのもので、yomiyasuスキルと併用できます。

入っているものは4つです。

| 部品 | 働き | 反映 |
|---|---|---|
| `output-styles/yomiyasu-chat.md` | 文体の原則。毎回の応答に効く | 編集後はClaude Codeの再起動 |
| `hooks/yomiyasu_stop_hook.py` | 応答が終わるたびに `yomiyasu_lint` と個人パターンで採点し、表示と記録をする | 即時 |
| `skills/style-feedback` | `/yomiyasu-chat:style-feedback` で読みにくかった文を取り込み、個人パターンとルールを育てる | 即時 |
| `scripts/` | 手動で採点する `yomiyasu-lint`、直近の応答を調べる `lint-last-response.py`、記録を集計する `lint-log-summary.py` | 即時 |

採点には、インストール済みのyomiyasuプラグインに同梱の `yomiyasu_lint.py` を使います。

```text
/plugin marketplace add nanaism/yomiyasu
/plugin install yomiyasu@yomiyasu
```

## 使い方

### プラグインとして使う（推奨）

```text
/plugin marketplace add atimot/yomiyasu-chat
/plugin install yomiyasu-chat@yomiyasu-chat
```

Stop hookとスキルは自動で有効です。output styleはプラグイン名付きの `yomiyasu-chat:yomiyasu-chat` として登録されるので、`/output-style yomiyasu-chat:yomiyasu-chat` で選ぶか、`~/.claude/settings.json` に次を書きます。値は大文字小文字を区別するので注意してください。

```json
{ "outputStyle": "yomiyasu-chat:yomiyasu-chat" }
```

プラグインの記録と個人パターンは `~/.claude/plugins/data/yomiyasu-chat-yomiyasu-chat/` に置かれ、プラグインを更新しても残ります。

### シンボリックリンクで使う（文面を直しながら使うとき）

```bash
git clone https://github.com/atimot/yomiyasu-chat.git ~/work/yomiyasu-chat
mkdir -p ~/.claude/output-styles
ln -s ~/work/yomiyasu-chat/output-styles/yomiyasu-chat.md ~/.claude/output-styles/yomiyasu-chat.md
```

`~/.claude/settings.json` に `"outputStyle": "yomiyasu-chat"` を書き、Stop hookを次のように登録してClaude Codeを再起動します。プラグインとして入れた場合はこの設定は不要です。

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/work/yomiyasu-chat/hooks/yomiyasu_stop_hook.py\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

この運用では記録と個人パターンは `~/.claude/yomiyasu-chat/` に置かれます。`/yomiyasu-chat:style-feedback` はプラグインのスキルなので、この運用で使うには `skills/style-feedback` を `~/.claude/skills/style-feedback` にリンクします。プラグインとシンボリックリンクを同時に使うと同名のスタイルが二重に登録されるので、どちらか一方にしてください。

## 導入の順番と基準値

効果を数字で比べられるように、スタイルを有効にする前に素の点数を記録しておきます。

1. yomiyasuプラグインを入れる
2. このプラグインを入れる。output styleは `Default` のまま数日使う。Stop hookが素の応答の点数を記録する
3. `/output-style yomiyasu-chat:yomiyasu-chat` に切り替える（シンボリックリンク運用なら `yomiyasu-chat`）
4. 1週間後に前後を比べる

```bash
scripts/lint-log-summary.py --split 2026-10-12   # 切り替えた日付の前後で件数・平均点・多い指摘を比べる
```

## 改善の進め方

読みにくい応答を見つけたら、その場で取り込んでください。

```text
/yomiyasu-chat:style-feedback 「読みにくかった文」 / 何が嫌か
```

文だけ渡した場合は、何が嫌だったかを1問だけ聞き返します。書き込む先は次の3か所です。

| 書き込む先 | 何を書くか | 反映 |
|---|---|---|
| `<データ置き場>/cases.md` | 台帳。元の文、何が嫌か、書き直し、分類 | 記録のみ |
| `<データ置き場>/patterns.tsv` | 特定の語や言い回しを正規表現で1行。Stop hookが `personal` ルールとして検出する | 次の応答から |
| `~/.claude/rules/yomiyasu-chat.md` | 同じ型の事例が2件目になったときだけ、NG → OKを1行。ユーザー rulesとして全プロジェクトに効く | 次のセッション（`/clear` 後） |

初回の事例をすぐルール化しないのは、ルールを太らせないためです。原則そのもの（結論の位置、箇条書きの使い方など）を変えたいときは、スキルがOutput Styleへの追記案を示し、ファイルは変えません。Output Styleはプラグインの更新で上書きされるので、リポジトリ側で直して再起動します。1回の変更は1ルールに絞り、同じ質問で前後を比べてください。

月に1回、記録を集計して多い指摘を見直し、`/doctor prompt-audit` でOutput Styleとルールの矛盾を検査します。点数は目安にとどめてください。yomiyasuの作者自身が、指標の最適化は不自然さを生むと書いています。

```bash
scripts/lint-log-summary.py            # 件数、平均点、指摘なしの割合、多いルール
```

## Stop hook

応答が終わるたびに最終応答を `yomiyasu_lint` に通し、個人パターンを重ねて採点します。yomiyasuが未インストールのとき、応答が200字未満のとき、日本語を含まないとき、検査に失敗したときは何もしません。採点はyomiyasuと同じ式（100点からwarn/errorは5点、infoは2点減点）を、無視ルールを除いて再計算します。

動作は環境変数で変えられます。

| 変数 | 既定 | 意味 |
|---|---|---|
| `YOMIYASU_HOOK_MODE` | `warn` | `warn` は警告表示のみ。`block` はスコアが閾値未満のとき1回だけ書き直しを求める。`off` で無効 |
| `YOMIYASU_HOOK_THRESHOLD` | `90` | `block` の閾値 |
| `YOMIYASU_HOOK_MIN_LEN` | `200` | この文字数未満の応答は検査しない |
| `YOMIYASU_HOOK_IGNORE` | 無し | 無視するルール名（カンマ区切り）。例: `unnatural_halfwidth_space` |
| `YOMIYASU_HOOK_LOG` | `<データ置き場>/lint-log.jsonl` | 検査結果の追記先。空文字で無効 |
| `YOMIYASU_LINT` | 無し | `yomiyasu_lint.py` のパスを直接指定 |

`block` は同じプロンプトに対して1回しか発動しないので、書き直しが延々と続くことはありません。まずは `warn` で指摘の傾向を見て、スタイルやパターンに反映するほうが、毎回の遅延とトークン消費を増やさずに済みます。

yomiyasuを入れない運用にしたいときは、`yomiyasu_lint.py`（MIT）のコピーをデータ置き場に置くとhookはそれを使います。コピーは自動では更新されません。

## スクリプト

```bash
scripts/yomiyasu-lint response.md            # 任意のMarkdownを検査
pbpaste | scripts/yomiyasu-lint              # クリップボードを検査
scripts/lint-last-response.py                # 直近のClaude Codeセッションの最終応答を検査（対象プロジェクトのディレクトリで実行）
scripts/lint-last-response.py -n 3 --cwd ~/work/some-project
scripts/lint-log-summary.py --split 2026-10-12
```

`yomiyasu_lint.py` の探索先は、環境変数 `YOMIYASU_LINT`、`~/.claude/plugins/installed_plugins.json` の記録、プラグインキャッシュの最新バージョン、`npx skills` の配置先、データ置き場のコピーの順です。

ルールが増えて回帰が気になり始めたら、`evals/` にケースを置いて `claude plugin eval .` でスタイルあり・なしのスコア差を測ります。

## 変更履歴

- 0.2.1: プラグインとして入れたときのoutput style名（`yomiyasu-chat:yomiyasu-chat`）をREADMEに明記
- 0.2.0: `/yomiyasu-chat:style-feedback` スキル、個人パターン `patterns.tsv`、無視ルール `YOMIYASU_HOOK_IGNORE`、記録の集計 `lint-log-summary.py` を追加。記録と個人パターンの置き場をプラグインのデータ置き場に移した。`yomiyasu_lint.py` のコピーをデータ置き場に置けばyomiyasu無しでも採点できるようにした
- 0.1.0: output styleとStop hookの初版

## ライセンス

MIT
