from __future__ import annotations

import argparse
import logging
import sys
from contextlib import ExitStack
from pathlib import Path

import pandas as pd

from analyzer import BrandAnalysisResult, Listing, analyze_brand, discover_additional_brands, save_results
from config import BRAND_ALIASES, BRAND_SELL_SPEED, OUTPUT_DIR, PRIMARY_SOURCE_SITES, PRIORITY_BRANDS, SOURCE_SITES, STRICT_MODEL_SEARCH_QUERIES, ScraperConfig
from scrapers import (
    AlluScraper,
    BrandearScraper,
    BrandOffScraper,
    KomehyoScraper,
    MercariScraper,
    RagtagScraper,
    RakutenScraper,
    RehelloScraper,
    RecloScraper,
    SecondStreetScraper,
    TrefacFashionScraper,
    VectorParkScraper,
    YahooShoppingScraper,
    ZozousedScraper,
)
from utils import build_output_csv_path, chunked, normalize_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="せどり利益商品検出ツール")
    parser.add_argument("--brands", type=str, default="", help='対象ブランド。例: "COACH,MARNI"')
    parser.add_argument("--min-profit-rate", type=float, default=0.3, help="最低利益率")
    parser.add_argument("--max-source-price", type=int, default=60000, help="仕入れ上限価格")
    parser.add_argument("--headless", type=str, default="true", help="Playwrightをヘッドレスで実行するか")
    parser.add_argument("--max-items", type=int, default=50, help="ブランドごとの取得件数上限")
    parser.add_argument("--batch-size", type=int, default=8, help="ブランドのバッチ実行単位")
    parser.add_argument("--deep-dive-brands", type=str, default="", help='深掘り判定するブランド。例: "POLENE"')
    parser.add_argument("--enable-auto-brand-discovery", type=str, default="true", help="自動ブランド探索を有効化するか")
    parser.add_argument("--full-source-scan", type=str, default="false", help="全仕入先サイトを走査するか")
    return parser.parse_args()


def str_to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_brand_list(value: str) -> list[str]:
    return [brand.strip() for brand in value.split(",") if brand.strip()]


def build_config(args: argparse.Namespace) -> ScraperConfig:
    user_specified_brands = bool(args.brands.strip())
    brands = parse_brand_list(args.brands) if user_specified_brands else PRIORITY_BRANDS.copy()
    deep_dive_brands = parse_brand_list(args.deep_dive_brands)
    if not deep_dive_brands and any(normalize_text(brand) == "polene" for brand in brands):
        deep_dive_brands = ["POLENE"]
    full_source_scan = str_to_bool(args.full_source_scan)
    active_source_sites = SOURCE_SITES.copy() if full_source_scan else PRIMARY_SOURCE_SITES.copy()
    return ScraperConfig(
        brands=brands,
        deep_dive_brands=deep_dive_brands,
        min_profit_rate=args.min_profit_rate,
        max_source_price=min(args.max_source_price, 60000),
        headless=str_to_bool(args.headless),
        max_items=args.max_items,
        batch_size=max(args.batch_size, 1),
        enable_auto_brand_discovery=str_to_bool(args.enable_auto_brand_discovery) and not user_specified_brands,
        user_specified_brands=user_specified_brands,
        full_source_scan=full_source_scan,
        active_source_sites=active_source_sites,
    )


def setup_logging() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def build_source_scrapers(config: ScraperConfig):
    scraper_factories = {
        "楽天市場": RakutenScraper,
        "Yahooショッピング": YahooShoppingScraper,
        "RAGTAG": RagtagScraper,
        "ZOZOUSED": ZozousedScraper,
        "ALLU": AlluScraper,
        "BRAND OFF": BrandOffScraper,
        "RECLO": RecloScraper,
        "KOMEHYO": KomehyoScraper,
        "2nd STREET": SecondStreetScraper,
        "ベクトルパーク": VectorParkScraper,
        "トレファクファッション": TrefacFashionScraper,
        "ブランディア": BrandearScraper,
        "Rehello by BOOKOFF": RehelloScraper,
    }
    return tuple(scraper_factories[site](config) for site in config.active_source_sites if site in scraper_factories)


def collect_brand_market_data(
    brand: str,
    mercari: MercariScraper,
    source_scrapers: list,
) -> tuple[list[Listing], list[Listing], dict[str, dict]]:
    sold_items = mercari.search(brand, sold=True)
    for alias in BRAND_ALIASES.get(brand, []):
        alias_sold = mercari.search(alias, sold=True)
        sold_items = sold_items + alias_sold
    for query in STRICT_MODEL_SEARCH_QUERIES.get(brand, []):
        model_sold = mercari.search(query, sold=True)
        sold_items = sold_items + model_sold
    source_items: list[Listing] = []
    site_stats: dict[str, dict] = {}
    for scraper in source_scrapers:
        items = scraper.search(brand)
        source_items.extend(items)
        site_stats[scraper.site_name] = dict(scraper.last_search_stats or {})
    return sold_items, source_items, site_stats


_ANSI_RED    = "\033[91m"
_ANSI_YELLOW = "\033[93m"
_ANSI_GRAY   = "\033[90m"
_ANSI_GREEN  = "\033[92m"
_ANSI_BOLD   = "\033[1m"
_ANSI_RESET  = "\033[0m"


def profit_label(gross_profit: int) -> str:
    return f"{_ANSI_GREEN}{_ANSI_BOLD}利益+{gross_profit:,}円{_ANSI_RESET}"

_RANK_LABEL = {
    "honmei": f"{_ANSI_RED}【本命】{_ANSI_RESET}",
    "hold":   f"{_ANSI_YELLOW}【保留】{_ANSI_RESET}",
    "skip":   f"{_ANSI_GRAY}【見送】{_ANSI_RESET}",
}

_SELL_SPEED_LABEL = {"fast": "高速", "medium": "中速", "slow": "低速"}


def rank_label(rank: str) -> str:
    return _RANK_LABEL.get(rank, f"【{rank}】")


def sell_speed_suffix(row: dict) -> str:
    speed = row.get("sell_speed") or BRAND_SELL_SPEED.get(str(row.get("brand", "")), "medium")
    label = _SELL_SPEED_LABEL.get(speed, "")
    return f"（{label}）" if label else ""


def summarize_to_console(text: str) -> None:
    print(text)


def apply_analysis_stats_to_sites(site_stats: dict[str, dict], result: BrandAnalysisResult, config: ScraperConfig) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for site in SOURCE_SITES:
        if site not in site_stats:
            stats = {
                "brand": result.sold_stats.brand if result.sold_stats else "",
                "site_name": site,
                "search_result_count": 0,
                "detail_page_count": 0,
                "in_stock_count": 0,
                "excluded_count": 0,
                "final_candidate_count": 0,
                "fetch_failed": False,
                "error_message": "",
                "status": "not_scanned" if site not in config.active_source_sites else "candidate_none",
            }
        else:
            stats = dict(site_stats.get(site, {}))
        stats["excluded_count"] = int(result.stats.site_excluded_count.get(site, 0))
        stats["final_candidate_count"] = int(result.stats.site_final_candidate_count.get(site, 0))
        merged[site] = stats
    return merged


def filter_final_rows(rows: list[dict], config: ScraperConfig) -> list[dict]:
    filtered = rows
    if config.user_specified_brands:
        target_brands = set(config.brands)
        filtered = [row for row in filtered if row["brand"] in target_brands]
    filtered = [row for row in filtered if row["source_site"] in SOURCE_SITES]
    filtered = [row for row in filtered if row["gross_profit"] >= config.final_output_min_profit]
    return filtered


def build_brand_site_summary(
    brand: str,
    site_stats: dict[str, dict],
    brand_rows: list[dict],
) -> list[str]:
    lines = ["- サイト別取得状況:"]
    final_rows_by_site: dict[str, list[dict]] = {}
    for row in brand_rows:
        final_rows_by_site.setdefault(row["source_site"], []).append(row)

    for site in SOURCE_SITES:
        stats = dict(site_stats.get(site, {}))
        if not stats:
            lines.append(f"  {site}: 未走査 | search=0 / detail=0 / in_stock=0 / excluded=0 / final=0")
            continue
        if stats.get("status") == "not_scanned":
            lines.append(f"  {site}: 未走査 | search=0 / detail=0 / in_stock=0 / excluded=0 / final=0")
            continue
        if stats.get("fetch_failed"):
            lines.append(f"  {site}: 取得失敗 ({stats.get('error_message', 'unknown error')})")
            continue
        final_count = len(final_rows_by_site.get(site, []))
        in_stock_count = int(stats.get("in_stock_count", 0))
        excluded_count = int(stats.get("excluded_count", max(in_stock_count - final_count, 0)))
        if final_count > 0:
            status_label = "候補あり"
        elif int(stats.get("search_result_count", 0)) > 0 or in_stock_count > 0:
            status_label = "候補なし"
        else:
            status_label = "候補なし"
        lines.append(
            f"  {site}: {status_label} | "
            f"search={int(stats.get('search_result_count', 0))} / "
            f"detail={int(stats.get('detail_page_count', 0))} / "
            f"in_stock={in_stock_count} / excluded={excluded_count} / final={final_count}"
        )
    return lines


def print_batch_summary(batch_index: int, batch_count: int, batch_brands: list[str], batch_results: list[BrandAnalysisResult], config: ScraperConfig) -> None:
    primary = sum(result.stats.primary_candidate_count for result in batch_results)
    sold_short = sum(result.stats.similar_sold_shortage_count for result in batch_results)
    out_of_stock = sum(result.stats.out_of_stock_excluded_count for result in batch_results)
    non_main = sum(result.stats.non_main_product_excluded_count for result in batch_results)
    model_mismatch = sum(result.stats.model_mismatch_hold_or_skip_count for result in batch_results)
    final_rows = [row for result in batch_results for row in result.rows if row["gross_profit"] >= config.final_output_min_profit]
    final_honmei = sum(1 for row in final_rows if row["candidate_rank"] == "honmei")
    final_hold = sum(1 for row in final_rows if row["candidate_rank"] == "hold")

    lines = [
        f"======== バッチ {batch_index}/{batch_count} ========",
        f"対象ブランド: {', '.join(batch_brands)}",
        f"1. gross_profit >= 3000 の一次候補件数: {primary}",
        f"2. 類似売り切れ件数不足で除外: {sold_short}",
        f"3. 在庫なしで除外: {out_of_stock}",
        f"4. 本体商品でないため除外: {non_main}",
        f"5. モデル不一致で保留/見送り: {model_mismatch}",
        f"6. 最終的な本命件数: {final_honmei}",
        f"7. 最終的な保留件数: {final_hold}",
        "",
    ]
    summarize_to_console("\n".join(lines))


def build_final_summary(
    final_rows: list[dict],
    brand_site_stats: dict[str, dict[str, dict]],
    analyzed_brand_count: int,
    auto_brand_count: int,
    output_path_text: str,
) -> str:
    if not final_rows:
        lines = [
            "利益候補は見つかりませんでした。",
            "",
            "ブランドごとのサイト別取得状況:",
        ]
        for brand, site_stats in brand_site_stats.items():
            lines.append(f"[{brand}]")
            lines.extend(build_brand_site_summary(brand, site_stats, []))
            lines.append("")
        lines.extend(
            [
                "======== 集計 ========",
                f"解析ブランド数: {analyzed_brand_count}",
                "利益候補ありブランド数: 0",
                f"自動追加ブランド数: {auto_brand_count}",
                "利益候補総数: 0件",
                "想定利益合計: +¥0",
                "最大利益候補: なし",
                f"CSV保存先: {output_path_text}",
            ]
        )
        return "\n".join(lines)

    df = pd.DataFrame(final_rows).sort_values(["gross_profit", "profit_rate"], ascending=[False, False]).reset_index(drop=True)
    lines: list[str] = ["ブランドごとのサイト別取得状況:"]
    profitable_brands = set(df["brand"].tolist())
    for brand, site_stats in brand_site_stats.items():
        lines.append(f"[{brand}]")
        brand_rows = df[df["brand"] == brand].to_dict("records") if brand in profitable_brands else []
        lines.extend(build_brand_site_summary(brand, site_stats, brand_rows))
        if brand not in profitable_brands:
            lines.append("- 利益候補: 0件")
        lines.append("")

    lines.append("利益候補の詳細:")
    for brand, group in df.groupby("brand", sort=False):
        rows = group.to_dict("records")
        honmei = [row for row in rows if row["candidate_rank"] == "honmei"]
        hold = [row for row in rows if row["candidate_rank"] == "hold"]
        site_counter: dict[str, int] = {}
        for row in rows:
            site_counter[row["source_site"]] = site_counter.get(row["source_site"], 0) + 1
        lines.append(f"[{brand}]")
        if site_counter:
            site_summary = " / ".join(f"{site} {count}件" for site, count in sorted(site_counter.items(), key=lambda item: (-item[1], item[0])))
            lines.append(f"- 候補が出たサイト: {site_summary}")
        if rows:
            first = rows[0]
            color_parts: list[str] = []
            for i in [1, 2, 3]:
                color = first.get(f"popularity_color_hint_top{i}", "unknown")
                count_val = int(first.get(f"popularity_color_top{i}_count", 0))
                ratio_val = float(first.get(f"popularity_color_top{i}_ratio", 0.0))
                if color and color != "unknown" and count_val > 0:
                    color_parts.append(f"{color} {count_val}件({ratio_val:.0%})")
            if color_parts:
                lines.append(f"- 人気色: {' / '.join(color_parts)}")
        lines.append(f"- 本命: {len(honmei)}件")
        for row in honmei[:3]:
            lines.append(
                f"  {rank_label('honmei')} {row['source_title']}  {profit_label(row['gross_profit'])}{sell_speed_suffix(row)}"
                f" | {row['source_site']} | 仕入¥{row['source_price']:,} | 色一致={'あり' if row['color_match'] else 'なし'}"
            )
        lines.append(f"- 保留: {len(hold)}件")
        for row in hold[:3]:
            lines.append(
                f"  {rank_label('hold')} {row['source_title']}  {profit_label(row['gross_profit'])}{sell_speed_suffix(row)}"
                f" | {row['source_site']} | 仕入¥{row['source_price']:,} | 色一致={'あり' if row['color_match'] else 'なし'}"
            )
        lines.append("")

    lines.append("本命・保留の中から gross_profit 上位5件:")
    for row in df.head(5).to_dict("records"):
        lines.append(
            f"  {rank_label(row['candidate_rank'])} {row['brand']} | {row['source_title']}  "
            f"{profit_label(row['gross_profit'])}{sell_speed_suffix(row)} | {row['source_site']} | 仕入¥{row['source_price']:,}"
        )

    lines.extend(
        [
            "",
            "======== 集計 ========",
            f"解析ブランド数: {analyzed_brand_count}",
            f"利益候補ありブランド数: {df['brand'].nunique()}",
            f"自動追加ブランド数: {auto_brand_count}",
            f"利益候補総数: {len(df)}件",
            f"想定利益合計: +¥{int(df['gross_profit'].sum()):,}",
            f"最大利益候補: {df.iloc[0]['source_title']}",
            f"CSV保存先: {output_path_text}",
        ]
    )
    return "\n".join(lines)


def run() -> int:
    args = parse_args()
    config = build_config(args)
    setup_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = build_output_csv_path(OUTPUT_DIR, config.brands)
    analyzed_brands: list[str] = []
    auto_brand_count = 0
    all_rows: list[dict] = []
    sold_cache: dict[str, list[Listing]] = {}
    brand_site_stats: dict[str, dict[str, dict]] = {}

    brand_batches = chunked(config.brands, config.batch_size)
    for batch_index, batch_brands in enumerate(brand_batches, start=1):
        batch_results: list[BrandAnalysisResult] = []
        with ExitStack() as stack:
            mercari = stack.enter_context(MercariScraper(config))
            source_scrapers = [stack.enter_context(scraper) for scraper in build_source_scrapers(config)]
            for brand in batch_brands:
                logging.info("ブランド解析を開始: %s", brand)
                analyzed_brands.append(brand)
                sold_items, source_items, site_stats = collect_brand_market_data(brand, mercari, source_scrapers)
                sold_cache[brand] = sold_items
                result = analyze_brand(brand, sold_items, source_items, config)
                brand_site_stats[brand] = apply_analysis_stats_to_sites(site_stats, result, config)
                batch_results.append(result)
                all_rows.extend(result.rows)
        print_batch_summary(batch_index, len(brand_batches), batch_brands, batch_results, config)
        save_results(filter_final_rows(all_rows, config), str(output_path))

    discovered_brands: list[dict] = []
    if config.enable_auto_brand_discovery:
        discovered_brands = discover_additional_brands(config.brands, sold_cache, config.auto_brand_limit)

    # user specified brands時は discovery無効のため、ここは通常空
    if discovered_brands:
        discovered_batches = chunked([item["brand"] for item in discovered_brands], config.batch_size)
        for batch_index, batch_brands in enumerate(discovered_batches, start=1):
            batch_results: list[BrandAnalysisResult] = []
            with ExitStack() as stack:
                mercari = stack.enter_context(MercariScraper(config))
                source_scrapers = [stack.enter_context(scraper) for scraper in build_source_scrapers(config)]
                for brand in batch_brands:
                    if brand in analyzed_brands:
                        continue
                    analyzed_brands.append(brand)
                    auto_brand_count += 1
                    sold_items, source_items, site_stats = collect_brand_market_data(brand, mercari, source_scrapers)
                    result = analyze_brand(brand, sold_items, source_items, config, auto_discovered_brand=True)
                    brand_site_stats[brand] = apply_analysis_stats_to_sites(site_stats, result, config)
                    batch_results.append(result)
                    all_rows.extend(result.rows)
            print_batch_summary(batch_index, len(discovered_batches), batch_brands, batch_results, config)
            save_results(filter_final_rows(all_rows, config), str(output_path))

    final_rows = filter_final_rows(all_rows, config)
    save_results(final_rows, str(output_path))
    try:
        output_path_text = str(output_path.relative_to(Path.cwd()))
    except ValueError:
        output_path_text = str(output_path)
    summary = build_final_summary(final_rows, brand_site_stats, len(analyzed_brands), auto_brand_count, output_path_text)
    summarize_to_console(summary)

    honmei_count = sum(1 for row in final_rows if row["candidate_rank"] == "honmei")
    hold_count = sum(1 for row in final_rows if row["candidate_rank"] == "hold")
    total_profit = sum(row["gross_profit"] for row in final_rows)
    print("\n========================================")
    print(f"　利益候補　{len(final_rows)} 件")
    print(f"　本命　　　{honmei_count} 件")
    print(f"　保留　　　{hold_count} 件")
    print(f"　想定利益　¥{total_profit:,}")
    print("========================================\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
