# せどり利益商品検出ツール

メルカリの売り切れ相場を基準に、国内向け中古販売チャネルから利益候補を抽出する Python 3.11+ 向け CLI ツールです。

## 機能

- 優先ブランドを最初に検索
- メルカリ売り切れデータから相場中央値・平均価格・売れた件数・人気色を集計
- 通常実行では `楽天市場 / Yahooショッピング / RAGTAG` を優先して仕入れ候補を取得
- 必要時のみ `--full-source-scan true` で全仕入先サイトを走査
- ブランド一致必須、型番・シリーズ・色・トークン類似度でマッチング
- 対象カテゴリは バッグ / リュック / 財布 / カードケース / 小物 のみ
- 利益率 30% 以上、かつ利益額 3,000円以上の候補のみ分析対象
- 最終CSVと日本語要約は `gross_profit >= 10,000円` の候補のみ出力
- メルカリ売り切れ件数 `5件以上` の候補のみ採用
- 仕入れ価格 `60,000円以下` を厳守
- 優先ブランド結果から、売れ筋バッグ系ブランドを最大10件まで自動追加
- 実行日時とブランド群を含むファイル名で `output/` に保存
- 実行後に人間向けの日本語要約を標準出力

## ディレクトリ構成

```text
config.py
app.py
analyzer.py
utils.py
scrapers/
  __init__.py
  base.py
  mercari.py
  rakuten.py
  yahoo_shopping.py
requirements.txt
README.md
```

## セットアップ

1. Python 3.11 以上を用意します。
2. 依存関係をインストールします。

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 実行方法

```bash
python app.py
```

ブランド指定ありの例:

```bash
python app.py --brands "COACH,MARNI" --min-profit-rate 0.3 --max-source-price 60000 --headless false --max-items 50 --enable-auto-brand-discovery true
```

全サイト走査したい場合:

```bash
python app.py --brands "COACH,MARNI" --full-source-scan true
```

## CLI オプション

- `--brands "COACH,MARNI"`
  - カンマ区切りで複数ブランドをまとめて指定可能
- `--min-profit-rate 0.3`
  - 最低利益率
- `--max-source-price 60000`
  - 仕入れ価格上限。コード上でも `60,000` に丸め込みます
- `--headless false`
  - Playwright をヘッドレスで実行するか
- `--max-items 50`
  - 各検索で見る最大件数
- `--enable-auto-brand-discovery true`
  - 自動追加ブランド探索を有効化
- `--full-source-scan true`
  - `ZOZOUSED / ALLU / BRAND OFF / RECLO / KOMEHYO / 2nd STREET / ベクトルパーク / トレファクファッション / ブランディア / Rehello by BOOKOFF` を含めた全仕入先サイトを走査

## 出力

- CSV:
  - 例: `output/profitable_items_20260315_120000_coach_marni.csv`
- 標準出力:
  - 利益候補が1件以上あるブランドだけを日本語で要約表示
  - ブランドごとのサイト別取得状況を表示
  - 未走査サイトは `未走査`、失敗サイトは `取得失敗` として区別
  - 各ブランドで利益額上位3件を表示
  - 最後に全体集計を表示

## 利益計算

```text
利益 = 売値 - メルカリ手数料10% - 想定送料 - 仕入れ値
利益率 = 利益 / 仕入れ値
```

送料仮定:

- 財布 / ウォレット / カードケース / コインケース / 名刺入れ: 210円
- ハンドバッグ / ショルダーバッグ / トートバッグ / バッグ: 750円
- リュック / バックパック / 大型バッグ: 850円
- その他: 520円

## 実装上の注意

- 各サイトの DOM は変更されるため、複数セレクタでフォールバックする実装にしています
- 一部サイトでは bot 対策やログイン制限で取得できないことがあります
- 取得失敗時はエラー終了せず、警告を出して次ブランドへ進みます
- 通常バッチでは `楽天市場 / Yahooショッピング / RAGTAG` を主戦場とし、他サイトは必要時のみ全走査する運用を想定しています
- 並び順は `gross_profit` 降順を優先します
- 色判定は複合色を扱い、`green/white` のように複数色を保持します
- メルカリの HTML 構造変更時は [scrapers/mercari.py](/C:/Users/talia/OneDrive/Desktop/sedori-search/scrapers/mercari.py) のセレクタ調整が必要です
- 商用利用や大量アクセス前に各サービスの利用規約を確認してください

## 補足

- 自動追加ブランドは `auto_discovered_brand=true` として CSV に残ります
- 自動追加ブランドの根拠は `note` 列に `売れ筋件数` と `バッグ系比率` を記録します
- 検索は必ず優先ブランドから開始し、その後に自動追加ブランドを解析します
