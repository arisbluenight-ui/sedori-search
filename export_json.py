import glob
import json
import os
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
