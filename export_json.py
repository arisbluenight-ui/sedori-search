import glob
import json
import os
import urllib.parse
from datetime import date
import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path("output")
DOCS_DIR = Path("docs")

RANK_MAP = {
    "honmei": "本命",
    "hold": "保留",
    "review": "要確認",
    "reject": "除外",
}

def export_latest_csv_to_json():
    files = glob.glob(str(OUTPUT_DIR / "profitable_items_*.csv"))
    if not files:
        print("CSVが見つかりません")
        return

    latest = max(files, key=os.path.getmtime)
    print(f"読み込み: {latest}")

    # エンコーディングを試行
    df = None
    for enc in ["utf-8-sig", "utf-8", "cp932", "shift_jis"]:
        try:
            df = pd.read_csv(latest, encoding=enc)
            print(f"エンコーディング: {enc}")
            break
        except Exception:
            continue

    if df is None:
        print("読み込み失敗")
        return

    # 列名正規化
    col_map = {
        "source_title":       "title",
        "gross_profit":       "profit",
        "estimated_sale_price": "mercari_price",
        "matched_sold_count": "sold_count",
        "model_signature":    "model_name",
        "primary_color":      "color",
        "color_match":        "color_match",
        "sell_speed":         "sell_speed",
    }
    df = df.rename(columns=col_map)

    # candidate_rank を日本語に
    if "candidate_rank" in df.columns:
        df["candidate_rank"] = df["candidate_rank"].map(RANK_MAP).fillna(df["candidate_rank"])

    # 数値の¥記号を除去
    for col in ["source_price", "profit", "mercari_price"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("¥", "").str.replace(",", "").str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # profit_rate を数値に
    if "profit_rate" in df.columns:
        df["profit_rate"] = pd.to_numeric(df["profit_rate"], errors="coerce").fillna(0).round(1)

    # unknownを空に
    for col in ["color", "model_name"]:
        if col in df.columns:
            df[col] = df[col].replace("unknown", "").replace("Unknown", "")

    # メルカリ検索URLを自動生成
    import urllib.parse
    def make_mercari_url(row):
        brand = str(row.get('brand', ''))
        title = str(row.get('source_title', '') or row.get('title', ''))
        # ブランド名 + タイトルの先頭30文字でキーワード作成
        keyword = f"{brand} {title}"[:40].strip()
        encoded = urllib.parse.quote(keyword)
        return f"https://jp.mercari.com/search?keyword={encoded}&status=sold_out"

    df['mercari_url'] = df.apply(make_mercari_url, axis=1)

    # NaNを空文字に
    df = df.fillna("")

    # docsフォルダに出力
    DOCS_DIR.mkdir(exist_ok=True)
    out_path = DOCS_DIR / "data.json"

    records = df.to_dict(orient="records")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "source_file": Path(latest).name,
            "items": records
        }, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(records)}件 -> {out_path} に出力しました")
    export_honmei_summary(df)

def export_honmei_summary(df: pd.DataFrame) -> None:
    honmei_df = df[df["candidate_rank"] == "本命"].copy()
    if honmei_df.empty:
        print("本命候補が0件のため honmei_summary.txt はスキップ")
        return

    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"【本命候補リスト - {today}】",
        "メルカリで以下の商品のSOLD件数と画像確認をお願いします。",
        "各商品について「SOLD2件以上あるか」「画像が一致するか」を確認してください。",
        "",
    ]

    for i, (_, item) in enumerate(honmei_df.iterrows(), 1):
        brand     = str(item.get("brand", "") or "")
        title     = str(item.get("title", "") or item.get("source_title", "") or "")
        model     = str(item.get("model_name", "") or "")
        color     = str(item.get("color", "") or "")
        site      = str(item.get("source_site", "") or "")
        src_p     = int(item.get("source_price", 0) or 0)
        profit    = int(item.get("profit", 0) or 0)
        src_url   = str(item.get("source_url", "") or "")
        mer_price = int(item.get("mercari_price", 0) or 0)

        search_keywords = " ".join(
            x for x in [
                brand,
                model if model and model != "unknown" else "",
                color if color and color != "unknown" else "",
                item.get("target_category") or "",
            ] if x
        )

        encoded = urllib.parse.quote(search_keywords)
        mercari_search = f"https://jp.mercari.com/search?keyword={encoded}&status=sold_out"

        lines += [
            f"{'='*50}",
            f"【{i}】{brand}",
            f"",
            f"■ 商品情報",
            f"  タイトル : {title[:50]}",
            f"  推定モデル: {model if model and model != 'unknown' else '不明（要確認）'}",
            f"  色      : {color if color and color != 'unknown' else '不明'}",
            f"  素材    : {item.get('material') or '不明'}",
            f"  形状    : {item.get('target_category') or '不明'}",
            f"  仕入れ先: {site}",
            f"  仕入値  : ¥{src_p:,} → 利益: +¥{profit:,}",
            f"  仕入URL : {src_url}",
            f"",
            f"■ メルカリSOLD確認用",
            f"  検索キーワード: {search_keywords}",
            f"  SOLD検索URL : {mercari_search}",
            f"",
            f"■ 確認ポイント（Claude in Chromeへ貼り付け用）",
            f"  以下をメルカリで検索し確認してください：",
            f"  「{search_keywords or f'{brand} {title[:25]}'}」",
            f"  ① SOLD件数が2件以上あるか",
            f"  ② 画像の形状・色・サイズ感が一致しているか",
            f"  ③ 同一モデルと判断できるか（別モデルでないか）",
            f"  ④ 直近のSOLD価格が ¥{mer_price:,} 前後か",
            f"",
        ]

    out_path = OUTPUT_DIR / "honmei_summary.txt"
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8-sig")
    print(f"OK: 本命{len(honmei_df)}件 -> {out_path} に出力しました")


def copy_dashboard_to_docs():
    import shutil
    src = Path("sedori_dashboard.html")
    dst = DOCS_DIR / "index.html"
    if src.exists():
        shutil.copy(src, dst)
        print(f"{src} -> {dst} にコピーしました")
    else:
        print(f"警告: {src} が見つかりません")

if __name__ == "__main__":
    export_latest_csv_to_json()
    copy_dashboard_to_docs()
    print()
    print("docs/ フォルダの中身:")
    for f in sorted(DOCS_DIR.iterdir()):
        print(f"   {f.name}  ({f.stat().st_size:,} bytes)")
    print()
    print("GitHub Pages 公開手順:")
    print("   1. git add docs/")
    print("   2. git commit -m 'update dashboard data'")
    print("   3. git push")
    print("   4. GitHubのSettings -> Pages -> Branch: main / folder: /docs")
