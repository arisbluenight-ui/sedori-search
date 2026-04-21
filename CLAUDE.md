# 私のルール

- code初心者なので、何をしたかは毎回**短くわかりやすく説明**してください
- **自動承認（yes）**で進めてください
- **結果は毎回 Discord に送ってください**
  - チャンネルID: `1485731974936269010`

---

# このプロジェクトについて

このリポジトリは、**メルカリの売り切れ相場を参照しつつ、日本国内で買いやすい中古販売チャネルからバッグ系ブランドの利益候補を探すせどりサーチツール**です。  
毎回ゼロから前提確認せず、このファイルを**最優先の固定前提**として扱ってください。

## 重要前提

- メルカリは**売却相場の参照専用**
- メルカリは**仕入れ候補に含めない**
- 仕入れ候補は**日本国内から気軽に買えるサイトを優先**
- このプロジェクトは **FrimaAPP ではない**
- 過去出品文の文体抽出、出品文生成、値下げ提案通知、再出品候補、コメント返信補助などの **FrimaAPP 文脈を混入させないこと**

## 通常運用の主戦場

- 楽天市場
- Yahooショッピング
- RAGTAG

## 通常運用から外しているもの

- ZOZOUSED は通常バッチから外している
- 必要な検証時のみ `full-source-scan` で確認する

## 全仕入れ候補サイト

- 楽天市場
- Yahooショッピング
- ZOZOUSED
- ALLU
- BRAND OFF
- RECLO
- KOMEHYO
- RAGTAG
- 2nd STREET
- ベクトルパーク
- トレファクファッション
- ブランディア
- Rehello by BOOKOFF

## 現在の条件

- `source_price <= 60000`
- `gross_profit >= 3000`
- 最終CSV / 日本語要約には `gross_profit >= 10000` のみ表示
- `profit_rate >= 0.3` を基本条件とするが、実行時に `--min-profit-rate 0.2` を使うことがある
- 類似売り切れ件数が少ない候補は保留寄りに扱う
- `mercari_sample_count` の下限条件あり
- 対象カテゴリは バッグ / リュック / 財布 / カードケース / 小物 のみ
- `--brands` 指定時は指定ブランド以外を混ぜない

## 除外条件

- 風
- ノベルティ
- 内ポケット
- インナーポーチ
- 付属品
- バッグインバッグ
- 本体以外
- ジャンク
- 難あり
- SOLD OUT
- 在庫なし
- お取り寄せ中
- 入荷待ち
- 売り切れ

## 在庫状態

- `source_url` が存在しても、在庫なし / SOLD OUT / お取り寄せ中 なら仕入れ候補に残さない
- `availability_status` を見て除外する
- 特に RAGTAG は SOLD OUT 混入が多かったため、リスト段階で SOLD OUT を除外する修正が入っている

## 色判定の方針

- `raw_color_text`, `primary_color`, `secondary_colors`, `detected_colors` を保持する
- `primary_color_band`, `secondary_color_bands`, `detected_color_bands` を保持する
- `popularity_color_hint_top1 / top2 / top3` および `popularity_color_hints` を保持する
- `popularity_color_band_top1 / top2 / top3` および `popularity_color_bands` を保持する
- `color_alignment` は `strong / neutral / flashy / unknown` を使う
- `note` に色判定理由を短く残す
- 配色物を単色ミスマッチ扱いしない

## 色判定ルール

- `popularity_color_band_top1` と一致する場合のみ本命寄りの強い色一致とする
- top2 / top3 一致は次点人気色として扱い、保留寄りにする
- `color_match = False` かつ `matched_sold_count < 5` の場合は本命にしない
- black / brown / white-beige 系は即除外しないが、件数が薄い時は保留に落とす
- flashy（red-pink など）は保留以下
- 色略称エイリアスは以下を考慮する
  - brown: `brw`, `bro`, `brn`
  - black: `bk`, `blk`
  - white: `wht`, `wh`
  - red: `rd`
  - blue: `nvy`, `nv`

## 色緩和ルール

- 直近5件の売り切れ実績の中で、**仕入れ候補と同系色の売れ実績が2件以上ある場合のみ**
  `flashy / unknown` を `neutral` に緩和する
- top1一致は引き続き `strong` のまま
- 「売れていること」だけではなく、**同系色であること** が必要

## 素材方針

- 基本は本革系バッグを優先する
- ただし布主体・キャンバス主体でも、相場が強く利益が出るブランドは除外しない
- A VACATION は布主体でも対象に残す
- 素材は除外条件ではなく加点要素として扱う

## コラボ判定の方針

- コラボ商品は除外しない
- 通常ラインとコラボ系は別枠で扱う
- 特に COACH は Rexy / 恐竜 / Disney / Peanuts などのコラボ・キャラ系が売れ筋になる場合がある
- コラボ系と通常ラインの相場を混ぜない
- `is_collab = True` を付けて分けて扱う

## 出力方針

- `source_url` は必ず実際の仕入れ候補ページURLにする
- 公式確認用リンクがある場合は `reference_url` など別列に分ける
- 比較に使った売り切れ実績URLも追えるようにする
- 日本語要約は利益候補が出たブランドだけを対象にする
- 【本命】【保留】を目立つ形で表示する
- 本命・保留の中から `gross_profit` 上位5件を出す
- 見送りは原則表示不要
- 全サイト分のサイト別サマリは 0件でも省略しない

## 現在の主な実装修正

- サイト別サマリ出力あり
  - `search_result_count`
  - `detail_page_count`
  - `in_stock_count`
  - `excluded_count`
  - `final_candidate_count`
  - `fetch_failure_count`
- 取得失敗 と 候補なし を分けて表示する
- 通常実行は主戦場3サイト優先
- `full-source-scan true` で全サイト確認可能
- 0件サイト群のセレクタ / URL 修正で復活したサイトあり
- RAGTAG は高速化修正済み
- SOLD OUT 混入修正済み
- color判定改善済み
- `candidate_rank` は見やすくする方向で改善中

## 開発運用メモ

- 開発は **Claude Code CLI** を使っている
- 初期は Codex から Claude Code へ移行した
- 移行過程で Claude 側がバグ修正や仕様変更をかなり加えているため、引き継ぎ文に未記載の変更が一部残っている可能性がある
- 前提は固定するが、必要以上に硬直的には扱わず、**実コード側の差分や実装済み変更も尊重**する
- 重要変更が多いため、区切りの良いところで commit / push したい

## 次スレや今後の修正で崩してはいけないこと

- メルカリ仕入れを復活させない
- コラボを除外しない
- 一般語だけでブランド判定しない
- ZOZOUSED を通常運用へ勝手に戻さない
- 色一致が弱いだけで無難色を機械的に即除外しない
- 逆に、次点人気色だけで安易に本命へ上げない

---

# コードの読み方

このプロジェクトでは、会話だけで判断せず、**必要に応じて主要ファイルを読んでから判断**してください。  
「こういう前提だったはず」と推測で進めず、該当ファイルを開いて確認してから提案・修正してください。

## 優先して参照してほしいファイル

- `analyzer.py`
  - 候補抽出、本命 / 保留 判定、色・モデル・Vision 連携の中心
- `config.py`
  - 固定条件、ブランド別設定、`NO_MODEL_REQUIRED_BRANDS` などの前提
- `vision_judge.py`
  - Vision 対象ブランド、Vision 判定ロジック、返り値の仕様
- `scrapers/rakuten.py`
- `scrapers/yahoo_shopping.py`
- `scrapers/vector_park.py`
- `scrapers/ragtag.py`
- `app.py`
- `run_dashboard.bat`

## 読み方のルール

- 判定理由を説明するときは、まず該当ファイルを読んでから答える
- 修正提案は、できるだけ**最小変更**で出す
- 既存の思想や運用を勝手に作り替えない
- 「確認用の一時変更」と「本番運用の変更」を分けて扱う
- 影響範囲が広い変更を提案する場合は、その前に局所的な案を優先する

---

# 回答スタイル

- 毎回このプロジェクトの説明を最初から繰り返さなくてよい
- この `CLAUDE.md` と関連コードを前提として会話する
- ただし、重要な判断に関わる部分は必ずコードを確認する
- 推測だけで断定しない
- 実装変更時は「どのファイルのどの部分を変えるか」を明確にする
- エラー原因の切り分けでは、まず以下の順で疑う
  1. 条件未達
  2. データ未取得
  3. 保存未反映
  4. 実装バグ

---

# このプロジェクトで今よく見る詰まり方

- 本命候補が出ない
- `color_alignment` が strong にならない
- `model_match` が弱い
- `source.image_urls` が空で Vision に入れない
- Vision は配線済みだが、候補が `hold` のためスキップされる
- CSV には列が出ても、実判定ではなく `SKIP:` のままになる

このような時は、まずコードと最新CSVを読んでから原因を切り分けてください。