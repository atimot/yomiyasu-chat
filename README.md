# yomiyasu-chat

Claude Codeの会話応答を、結論ファーストで読みやすい自然な日本語にするoutput styleです。[nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) の文体原則（主述の対応、擬人化と比喩動詞の排除、情報を足さない、太字と箇条書きの抑制など）を、推敲依頼時だけでなく毎回の応答に適用します。

yomiyasu本体は「渡された文章を書き直すスキル」であり、Claude Code自身の会話出力には適用されません。yomiyasu 2.0.2からは名前を出して頼んだときだけ使われ、毎回使うにはCLAUDE.mdに1行足す案内がありますが、その対象は記事やPRの説明文のような成果物の文章で、作業の報告や会話の応答は含みません。このリポジトリはその隙間を埋めるためのもので、yomiyasuスキルと併用できます。

入っているものは4つです。

| 部品 | 働き | 反映 |
|---|---|---|
| `output-styles/yomiyasu-chat.md` | 文体の原則。毎回の応答に適用される | 編集後はClaude Codeの再起動 |
| `hooks/yomiyasu_stop_hook.py` | 応答が終わるたびに `yomiyasu_lint` と個人パターンで採点し、表示と記録をする | 即時 |
| `skills/style-feedback` | `/yomiyasu-chat:style-feedback` で読みにくかった文を取り込み、個人パターンとルールを育てる | 即時 |
| `scripts/` | 手動で採点する `yomiyasu-lint`、直近の応答を調べる `lint-last-response.py`、記録を集計する `lint-log-summary.py` | 即時 |

採点には、インストール済みのyomiyasuプラグインに同梱の `yomiyasu_lint.py` を使います。yomiyasu 2.1.0で動作を確認しています（1.0.8の出力も読めます）。

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

Stop hookとスキルは自動で有効です。output styleはプラグイン名付きの `yomiyasu-chat:yomiyasu-chat` として登録されるので、`/output-style yomiyasu-chat:yomiyasu-chat` で選ぶか、`~/.claude/settings.json` に次を書きます。値の大文字小文字は区別されるので注意してください。

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

記録にはyomiyasuのバージョンと出力形式（`format_version`）も残ります。yomiyasuが更新されて検査ルールや点数の式が変わると同じ文章でも点が変わるので、バージョンをまたいだ点数は比べず、`--by-version` でバージョンごとに分けて見てください。yomiyasu 2.0.0で点数の式が変わったので、1.xの記録と2.xの記録はとくに比べないでください。

## 改善の進め方

読みにくい応答を見つけたら、その場で取り込んでください。

```text
/yomiyasu-chat:style-feedback 「読みにくかった文」 / 何が嫌か
```

文だけ渡した場合は、何が嫌だったかを1問だけ聞き返します。書き込む先は次の3か所です。

| 書き込む先 | 何を書くか | 反映 |
|---|---|---|
| `<データ置き場>/cases.md` | 事例集。元の文、何が嫌か、書き直し、分類 | 記録のみ |
| `<データ置き場>/patterns.tsv` | 特定の語や言い回しを正規表現で1行。Stop hookが `personal` ルールとして検出する | 次の応答から |
| `~/.claude/rules/yomiyasu-chat.md` | 同じ型の事例が2件目になったときだけ、NG → OKを1行。ユーザー単位のrulesとして全プロジェクトに反映される | 次のセッション（`/clear` 後） |

初回の事例をすぐルール化しないのは、ルールを増やしすぎないためです。原則そのもの（結論の位置、箇条書きの使い方など）を変えたいときは、スキルがoutput styleへの追記案を示し、ファイルは変えません。output styleはプラグインの更新で上書きされるので、リポジトリ側で直して再起動します。1回の変更は1ルールに絞り、同じ質問で前後を比べてください。

月に1回、記録を集計して多い指摘を見直し、`/doctor prompt-audit` でoutput styleとルールの矛盾を検査します。点数は目安にとどめてください。yomiyasuの作者自身が、指標の最適化は不自然さを生むと書いています。

```bash
scripts/lint-log-summary.py            # 件数、平均点、指摘なしの割合、多いルール
```

## Stop hook

応答が終わるたびに最終応答を `yomiyasu_lint` に通し、個人パターンを重ねて見直し候補を集めます。yomiyasuが未インストールのとき、応答が200字未満のとき、日本語を含まないとき、検査に失敗したときは何もしません。

表示する点数は、yomiyasu 2.0.0以降の `rule_penalty_score` と同じ式で出す目安です。候補の重み（error 3、warn 2、info 1。`excess_bold` と `excess_list` は文書単位で2、`bold_label_list` は1）を地の文1,000字あたりに直した x から、100×40÷(40+x) を丸めます。候補が無ければ100、あれば1〜99です。無視ルールも個人パターンも無ければyomiyasuの値をそのまま使い、あるときは同じ式で計算し直します（計算し直すときの字数は見出しを含む `metrics.char_count` なので、yomiyasuの値と数点ずれることがあります）。yomiyasu 1.xの出力には当時の式（100点からwarn/errorは5点、infoは2点減点）を使います。yomiyasu自身はこの値を合否に使わない目安としていて、通常の出力には出しません。1,000字以下の応答では、warn 1件で95、2件で91、3件で87です。

動作は環境変数で変えられます。

| 変数 | 既定 | 意味 |
|---|---|---|
| `YOMIYASU_HOOK_MODE` | `warn` | `warn` は警告表示のみ。`block` はスコアが閾値未満のとき1回だけ書き直しを求める。`off` で無効 |
| `YOMIYASU_HOOK_THRESHOLD` | `90` | `block` の閾値。目安の点数がこの値未満のとき書き直しを求める。1,000字以下の応答ではwarn 3件で87になり閾値を下回る |
| `YOMIYASU_HOOK_MIN_LEN` | `200` | この文字数未満の応答は検査しない |
| `YOMIYASU_HOOK_IGNORE` | 無し | 無視するルール名（カンマ区切り）。例: `sentence_end_repetition` |
| `YOMIYASU_HOOK_LOG` | `<データ置き場>/lint-log.jsonl` | 検査結果（点数、ルール名、yomiyasuのバージョン、出力形式）の追記先。空文字で無効 |
| `YOMIYASU_LINT` | 無し | `yomiyasu_lint.py` のパスを直接指定 |

`block` は同じプロンプトに対して1回しか発動しないので、書き直しが延々と続くことはありません。まずは `warn` で指摘の傾向を見て、スタイルやパターンに反映するほうが、毎回の遅延とトークン消費を増やさずに済みます。

yomiyasuを入れない運用にしたいときは、`yomiyasu_lint.py` と `markdown_visibility.py`（どちらもMIT）の2ファイルをデータ置き場に置きます。`yomiyasu_lint.py` は同じディレクトリの `markdown_visibility.py` を読み込むので、1ファイルだけでは動きません。yomiyasu 2.1.0でもこの2ファイルで動きます。hookはこのコピーを使いますが、コピーは自動では更新されません。

## スクリプト

```bash
scripts/yomiyasu-lint response.md            # 任意のMarkdownを検査
pbpaste | scripts/yomiyasu-lint              # クリップボードを検査
scripts/lint-last-response.py                # 直近のClaude Codeセッションの最終応答を検査（対象プロジェクトのディレクトリで実行）
scripts/lint-last-response.py -n 3 --cwd ~/work/some-project
scripts/lint-log-summary.py --split 2026-10-12
scripts/lint-log-summary.py --by-version     # yomiyasuのバージョンごとに分けて集計
```

`yomiyasu_lint.py` の探索先は、環境変数 `YOMIYASU_LINT`、`~/.claude/plugins/installed_plugins.json` の記録、プラグインキャッシュの最新バージョン、`npx skills` の配置先、データ置き場のコピー（2ファイルそろっているとき）の順です。見つけた `yomiyasu_lint.py` のバージョンは、2.0.0以降はファイル内の `__version__`、1.xは `.claude-plugin/plugin.json` から読みます。

ルールが増えて回帰が気になり始めたら、`evals/` にケースを置いて `claude plugin eval .` でスタイルあり・なしのスコア差を測ります。

## 変更履歴

- 0.3.0: yomiyasu 2.1.0に追従。Stop hookの点数を2.0.0以降の `rule_penalty_score` と同じ式に変え、表示を「見直し候補n件（目安m）」にし、記録に `format_version` を足した。`yomiyasu_lint.py` のバージョンをファイル内の `__version__` から読むようにした。output styleに1.1.0から2.1.0までの原則を反映した（定型の導入と結び、数の宣言、「もちろん、」の短文、「〜のは、A、B、C。」の強調形、評価語だけの短文の連続、目的語の省略、主題の「は」の掛かる範囲、漢語を詰めた句、「〜を行う」、許可・能力・義務・保証の言い方、推量や伝聞の断定化、間を作るだけの読点、「〜ためです。」の切り出し、箇条書きのラベルとコロン、見出しの項目名化、「まとめ」見出し、罫線文字、補助動詞と形式名詞のひらがな書き、相対の日付）
- 0.2.3: yomiyasu 1.0.8に追従。廃止されたルール `unnatural_halfwidth_space` の例を差し替え、output styleから和欧文間の半角空白の行を外した（yomiyasuが空白の有無を一律には扱わない方針に変わったため）。`yomiyasu_lint.py` のコピー運用を `markdown_visibility.py` との2ファイルに変更。記録にyomiyasuのバージョンを残し、`lint-log-summary.py --by-version` で分けて集計できるようにした。output styleに変更報告の書き方と専門用語の扱いを追加
- 0.2.2: 文面をyomiyasuの文体ルールにそろえた。禁止語「効く」「壊れる」の置き換え、SKILL.mdとスクリプトの和欧文間の空白の除去、「output style」の表記統一、plugin.jsonのスキル名を `/yomiyasu-chat:style-feedback` に修正
- 0.2.1: プラグインとして入れたときのoutput style名（`yomiyasu-chat:yomiyasu-chat`）をREADMEに明記
- 0.2.0: `/yomiyasu-chat:style-feedback` スキル、個人パターン `patterns.tsv`、無視ルール `YOMIYASU_HOOK_IGNORE`、記録の集計 `lint-log-summary.py` を追加。記録と個人パターンの置き場をプラグインのデータ置き場に移した。`yomiyasu_lint.py` のコピーをデータ置き場に置けばyomiyasu無しでも採点できるようにした
- 0.1.0: output styleとStop hookの初版

## ライセンス

MIT
