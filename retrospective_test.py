"""
retrospective_test.py
過去成功商品の本番経路リトロスペクティブ検証ツール

使い方:
  python retrospective_test.py \
      --input local_test_data/retrospective_cases.csv \
      --output local_test_data/reports/

  # 診断Vision追加実行
  python retrospective_test.py \
      --input local_test_data/retrospective_cases.csv \
      --output local_test_data/reports/ \
      --run-vision true \
      --vision-max-cases 5 \
      --vision-max-sold-per-case 3

入力CSV列:
  case_id, brand, model, color, size, source_site, source_title, source_url,
  source_image_path_or_url, source_price, sold_price, sold_period_days, notes

出力:
  local_test_data/reports/retrospective_<timestamp>.csv
  local_test_data/reports/retrospective_<timestamp>.md
"""
from __future__ import annotations

import argparse
import csv
import datetime
import logging
import sys
from pathlib import Path

import pandas as pd

from analyzer import BrandAnalysisResult, Listing, analyze_brand, classify_candidate_rank
from config import BRAND_ALIASES, SOURCE_SITES, STRICT_MODEL_SEARCH_QUERIES, ScraperConfig
from scrapers import MercariScraper
from utils import is_target_category


OUTPUT_CSV_COLUMNS = [
    "case_id", "brand", "model", "color",
    "source_title", "source_price",
    "matched_sold_count", "matched_sold_titles",
    "matched_sold_urls", "matched_sold_image_urls",
    "preliminary_rank",
    "production_vision_executed",
    "production_vision_confirmed", "production_vision_near",
    "production_vision_rejected", "production_vision_summary",
    "production_rank",
    "diagnostic_vision_executed",
    "diagnostic_vision_confirmed", "diagnostic_vision_near",
    "diagnostic_vision_rejected", "diagnostic_vision_summary",
    "stopped_at_stage", "stop_reason",
]

_FALLBACK_SITE = "楽天市場"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="過去成功商品の本番経路リトロスペクティブ検証")
    p.add_argument("--input", required=True, help="入力CSVパス")
    p.add_argument("--output", required=True, help="出力ディレクトリ")
    p.add_argument("--run-vision", default="false", help="診断Visionを追加実行するか (true/false)")
    p.add_argument("--vision-max-cases", type=int, default=10, help="診断Vision実行上限ケース数")
    p.add_argument("--vision-max-sold-per-case", type=int, default=3, help="ケースごとのSOLD比較上限数")
    p.add_argument("--min-profit-rate", type=float, default=0.3, help="最低利益率（本番同値）")
    p.add_argument("--max-source-price", type=int, default=60000, help="仕入れ上限価格（本番同値）")
    return p.parse_args()


def _str_to_bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


def _build_config(args: argparse.Namespace) -> ScraperConfig:
    return ScraperConfig(
        min_profit_rate=args.min_profit_rate,
        max_source_price=args.max_source_price,
        headless=True,
        user_specified_brands=True,
    )


def _collect_sold_items(brand: str, mercari: MercariScraper) -> list[Listing]:
    sold: list[Listing] = list(mercari.search(brand, sold=True))
    for alias in BRAND_ALIASES.get(brand, []):
        sold += mercari.search(alias, sold=True)
    for query in STRICT_MODEL_SEARCH_QUERIES.get(brand, []):
        sold += mercari.search(query, sold=True)
    return sold


def _build_listing(case: dict) -> Listing:
    site = (case.get("source_site") or "").strip()
    if not site or site not in SOURCE_SITES:
        site = _FALLBACK_SITE
    image_field = (case.get("source_image_path_or_url") or "").strip()
    image_urls = [image_field] if image_field else []
    try:
        price = int(float(case.get("source_price", 0) or 0))
    except (ValueError, TypeError):
        price = 0
    return Listing(
        brand=(case.get("brand") or "").strip(),
        title=(case.get("source_title") or "").strip(),
        price=price,
        url=(case.get("source_url") or "").strip(),
        site=site,
        sold=False,
        metadata={"availability_status": "available"},
        image_urls=image_urls,
    )


def _production_vision_executed(row: dict) -> bool:
    return not str(row.get("vision_summary", "")).startswith("SKIP:")


def _run_diagnostic_vision(
    listing: Listing,
    sold_items: list[Listing],
    brand: str,
    model_hint: str,
    max_sold: int,
) -> dict:
    """
    診断Vision。production_rankには影響しない。
    本番と同じvision_compare_sold_items()を使い、呼び出し条件だけ強制する。
    """
    from vision_judge import vision_compare_sold_items

    filtered = [s for s in sold_items if is_target_category(s.title)]
    sold_for_vision = [
        {
            "item_url": s.url,
            "title": s.title,
            "price": getattr(s, "price", 0),
            "image_urls": s.image_urls,
        }
        for s in filtered[:max_sold]
        if s.image_urls
    ]

    if not sold_for_vision:
        return {
            "executed": True,
            "confirmed": 0, "near": 0, "rejected": 0,
            "summary": "SOLD画像なし",
        }

    try:
        r = vision_compare_sold_items(
            source_item={
                "title": listing.title,
                "price": listing.price,
                "item_url": listing.url,
                "image_urls": listing.image_urls,
            },
            mercari_sold_items=sold_for_vision,
            brand=brand,
            model_hint=model_hint,
        )
        return {
            "executed": True,
            "confirmed": r["sold_count_vision_confirmed"],
            "near": r["sold_count_near_variant"],
            "rejected": r["vision_reject_count"],
            "summary": r["vision_reason_summary"],
        }
    except Exception as exc:
        logging.warning("診断Visionエラー: %s", exc)
        return {
            "executed": True,
            "confirmed": 0, "near": 0, "rejected": 0,
            "summary": f"エラー: {exc}",
        }


def _process_case(
    case: dict,
    sold_items: list[Listing],
    config: ScraperConfig,
    run_vision: bool,
    vision_max_sold: int,
) -> dict:
    brand = (case.get("brand") or "").strip()
    out: dict = {
        "case_id": case.get("case_id", ""),
        "brand": brand,
        "model": case.get("model", ""),
        "color": case.get("color", ""),
        "source_title": case.get("source_title", ""),
        "source_price": case.get("source_price", ""),
        "matched_sold_count": "",
        "matched_sold_titles": "",
        "matched_sold_urls": "",
        "matched_sold_image_urls": "",
        "preliminary_rank": "",
        "production_vision_executed": False,
        "production_vision_confirmed": "",
        "production_vision_near": "",
        "production_vision_rejected": "",
        "production_vision_summary": "",
        "production_rank": "",
        "diagnostic_vision_executed": False,
        "diagnostic_vision_confirmed": "",
        "diagnostic_vision_near": "",
        "diagnostic_vision_rejected": "",
        "diagnostic_vision_summary": "",
        "stopped_at_stage": "",
        "stop_reason": "",
    }

    filtered_sold = [s for s in sold_items if is_target_category(s.title)]
    if not filtered_sold:
        out["stopped_at_stage"] = "mercari_retrieval"
        out["stop_reason"] = "対象カテゴリのSOLD件数=0"
        return out

    listing = _build_listing(case)
    result: BrandAnalysisResult = analyze_brand(brand, sold_items, [listing], config)

    if result.sold_stats is None:
        out["stopped_at_stage"] = "mercari_retrieval"
        out["stop_reason"] = "対象カテゴリのSOLD件数=0"
        return out

    if result.sold_stats.sample_count < config.min_mercari_sample_count:
        out["stopped_at_stage"] = "mercari_retrieval"
        out["stop_reason"] = (
            f"SOLD件数不足"
            f"(sample_count={result.sold_stats.sample_count}"
            f" < {config.min_mercari_sample_count})"
        )
        return out

    if not result.rows:
        out["stopped_at_stage"] = "analyze_brand_filters"
        out["stop_reason"] = "条件未達（タイトル除外/モデル/価格/利益/SOLD件数いずれか）"
        return out

    row = result.rows[0]

    # matched_sold_image_urls: Mercari SOLD一覧からURLで逆引き
    sold_url_to_img = {
        s.url: (s.image_urls[0] if s.image_urls else "")
        for s in sold_items
    }
    matched_urls = [u.strip() for u in str(row.get("matched_sold_urls", "")).split("|") if u.strip()]
    matched_imgs = [sold_url_to_img.get(u, "") for u in matched_urls]

    prod_vision_exec = _production_vision_executed(row)

    # preliminary_rank: Vision実行前のランク。classifyに使うフィールドはVisionで変更されないため再計算可。
    out.update({
        "matched_sold_count": row.get("matched_sold_count", 0),
        "matched_sold_titles": row.get("matched_sold_titles", ""),
        "matched_sold_urls": row.get("matched_sold_urls", ""),
        "matched_sold_image_urls": " | ".join(matched_imgs),
        "preliminary_rank": classify_candidate_rank(row),
        "production_vision_executed": prod_vision_exec,
        "production_vision_confirmed": row.get("vision_confirmed", "") if prod_vision_exec else "",
        "production_vision_near": row.get("vision_near", "") if prod_vision_exec else "",
        "production_vision_rejected": row.get("vision_rejected", "") if prod_vision_exec else "",
        "production_vision_summary": row.get("vision_summary", ""),
        "production_rank": row.get("candidate_rank", ""),
    })

    if run_vision and listing.image_urls:
        dv = _run_diagnostic_vision(
            listing, sold_items, brand,
            row.get("model_signature", ""),
            vision_max_sold,
        )
        out.update({
            "diagnostic_vision_executed": dv["executed"],
            "diagnostic_vision_confirmed": dv["confirmed"],
            "diagnostic_vision_near": dv["near"],
            "diagnostic_vision_rejected": dv["rejected"],
            "diagnostic_vision_summary": dv["summary"],
        })
    elif run_vision and not listing.image_urls:
        out["diagnostic_vision_executed"] = False
        out["diagnostic_vision_summary"] = "スキップ: 画像なし"

    return out


def _write_csv(rows: list[dict], output_dir: Path, ts: str) -> Path:
    path = output_dir / f"retrospective_{ts}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_markdown(cases_input: list[dict], rows: list[dict], output_dir: Path, ts: str) -> Path:
    path = output_dir / f"retrospective_{ts}.md"
    case_map = {str(c.get("case_id", "")): c for c in cases_input}
    lines: list[str] = [
        f"# Retrospective Test Report",
        f"",
        f"生成日時: {ts}",
        f"",
        f"---",
        f"",
    ]

    for row in rows:
        cid = str(row.get("case_id", ""))
        inp = case_map.get(cid, {})
        brand = row.get("brand", "")
        model = row.get("model", "")
        color = row.get("color", "")
        lines.append(f"## Case {cid}: {brand} / {model} / {color}")
        lines.append("")
        lines.append("### 入力情報")
        lines.append("")
        lines.append(f"- タイトル: {row.get('source_title', '')}")
        try:
            price_disp = f"¥{int(float(str(row.get('source_price', 0) or 0))):,}"
        except (ValueError, TypeError):
            price_disp = str(row.get("source_price", ""))
        lines.append(f"- 仕入れ価格: {price_disp}")
        lines.append(f"- 販売サイト: {inp.get('source_site', '')}")
        src_url = inp.get("source_url", "") or ""
        lines.append(f"- 仕入れURL: {src_url if src_url else '（なし）'}")
        img_field = inp.get("source_image_path_or_url", "") or ""
        lines.append(f"- 画像: {img_field if img_field else '（なし）'}")
        sold_p = inp.get("sold_price", "") or ""
        if sold_p:
            try:
                lines.append(f"- 実際の売却価格: ¥{int(float(sold_p)):,}")
            except (ValueError, TypeError):
                lines.append(f"- 実際の売却価格: {sold_p}")
        days = inp.get("sold_period_days", "") or ""
        if days:
            lines.append(f"- 売却日数: {days}日")
        notes = inp.get("notes", "") or ""
        if notes:
            lines.append(f"- メモ: {notes}")
        lines.append("")

        if row.get("stopped_at_stage"):
            lines.append("### 判定停止")
            lines.append("")
            lines.append(f"- 停止ステージ: `{row['stopped_at_stage']}`")
            lines.append(f"- 停止理由: {row['stop_reason']}")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        lines.append("### 参照SOLD一覧")
        lines.append("")
        titles = [t.strip() for t in str(row.get("matched_sold_titles", "")).split("|") if t.strip()]
        urls = [u.strip() for u in str(row.get("matched_sold_urls", "")).split("|") if u.strip()]
        imgs = [i.strip() for i in str(row.get("matched_sold_image_urls", "")).split("|") if i.strip()]
        if titles:
            for i, title in enumerate(titles):
                url = urls[i] if i < len(urls) else ""
                img = imgs[i] if i < len(imgs) else ""
                entry = f"{i + 1}. {f'[{title}]({url})' if url else title}"
                lines.append(entry)
                if img:
                    lines.append(f"   ![image]({img})")
        else:
            lines.append("（マッチなし）")
        lines.append("")

        lines.append("### 本番判定結果")
        lines.append("")
        lines.append(f"- **preliminary_rank**: `{row.get('preliminary_rank', '')}`")
        lines.append(f"- **production_rank**: `{row.get('production_rank', '')}`")
        lines.append(f"- Vision実行: {row.get('production_vision_executed', False)}")
        if row.get("production_vision_executed"):
            lines.append(f"  - confirmed: {row.get('production_vision_confirmed', '')}")
            lines.append(f"  - near: {row.get('production_vision_near', '')}")
            lines.append(f"  - rejected: {row.get('production_vision_rejected', '')}")
            lines.append(f"  - summary: {row.get('production_vision_summary', '')}")
        lines.append("")

        if row.get("diagnostic_vision_executed"):
            lines.append("### 診断Vision結果（※production_rankに非反映）")
            lines.append("")
            lines.append(f"- confirmed: {row.get('diagnostic_vision_confirmed', '')}")
            lines.append(f"- near: {row.get('diagnostic_vision_near', '')}")
            lines.append(f"- rejected: {row.get('diagnostic_vision_rejected', '')}")
            lines.append(f"- summary: {row.get('diagnostic_vision_summary', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    run_vision = _str_to_bool(args.run_vision)
    config = _build_config(args)

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = pd.read_csv(input_path, dtype=str).fillna("").to_dict(orient="records")
    logging.info("ケース数: %d", len(cases))

    # ブランド別にグループ化（順序保持）
    brands_in_order: list[str] = []
    by_brand: dict[str, list[dict]] = {}
    for c in cases:
        brand = (c.get("brand") or "").strip()
        if brand not in by_brand:
            brands_in_order.append(brand)
            by_brand[brand] = []
        by_brand[brand].append(c)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_rows: list[dict] = []
    vision_case_count = 0

    with MercariScraper(config) as mercari:
        for brand in brands_in_order:
            cases_for_brand = by_brand[brand]
            logging.info("[%s] Mercari SOLD取得中...", brand)
            sold_items = _collect_sold_items(brand, mercari)
            logging.info("[%s] SOLD件数: %d", brand, len(sold_items))

            for case in cases_for_brand:
                cid = case.get("case_id", "?")
                logging.info("[%s] case_id=%s 判定中...", brand, cid)

                do_vision = run_vision and vision_case_count < args.vision_max_cases
                row = _process_case(case, sold_items, config, do_vision, args.vision_max_sold_per_case)

                if do_vision and row.get("diagnostic_vision_executed"):
                    vision_case_count += 1

                output_rows.append(row)
                stage = row.get("stopped_at_stage")
                if stage:
                    logging.info("[%s] case_id=%s → 停止: %s / %s", brand, cid, stage, row.get("stop_reason"))
                else:
                    logging.info(
                        "[%s] case_id=%s → production_rank=%s preliminary=%s",
                        brand, cid,
                        row.get("production_rank"),
                        row.get("preliminary_rank"),
                    )

    csv_path = _write_csv(output_rows, output_dir, ts)
    md_path = _write_markdown(cases, output_rows, output_dir, ts)
    logging.info("CSV: %s", csv_path)
    logging.info("Markdown: %s", md_path)
    print(f"\n出力完了:\n  CSV: {csv_path}\n  MD:  {md_path}")


if __name__ == "__main__":
    main()
