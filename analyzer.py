from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable
import logging
import re

logger = logging.getLogger(__name__)

import pandas as pd
from rapidfuzz import fuzz

from condition_filter import (
    normalize_condition,
    extract_condition_from_text,
    check_description_words,
    ALLOWED_RANKS,
    REVIEW_RANKS,
    REJECT_RANKS,
)
from config import (
    AMBIGUOUS_BRANDS,
    BAG_KEYWORDS,
    BRAND_ALIASES,
    BRAND_MAX_PRICE,
    BRAND_MAX_PRICE_REVIEW,
    BRAND_SELL_SPEED,
    COLOR_RULES,
    DISCOVERY_EXCLUDED_TERMS,
    NO_MODEL_REQUIRED_BRANDS,
    SOURCE_SITES,
    STRICT_MODEL_BRANDS,
    ScraperConfig,
)
from utils import (
    contains_bag_keyword,
    contains_excluded_candidate_term,
    detect_color,
    detect_colors,
    detect_target_category,
    evaluate_color_alignment,
    extract_iacucci_model,
    extract_line_tokens,
    extract_marni_model,
    extract_material_tokens,
    extract_model_tokens,
    extract_polene_model,
    extract_size_tokens,
    extract_color_features,
    format_yen,
    guess_shipping_fee,
    is_main_product,
    is_target_category,
    is_unavailable_status,
    most_common_color,
    normalize_text,
    pick_representative_keywords,
    safe_average,
    safe_median,
    tokenize,
    top_common_color_bands,
    top_common_colors,
)


DISCOVERY_STOPWORDS = {
    normalize_text(term)
    for term in (
        set(DISCOVERY_EXCLUDED_TERMS)
        | set(BAG_KEYWORDS)
        | set(AMBIGUOUS_BRANDS)
        | set(COLOR_RULES.keys())
        | {variant for variants in COLOR_RULES.values() for variant in variants}
    )
}


POLENE_SIGNATURE_LABELS = {
    "numero-un": "Numero Un",
    "numero-sept": "Numero Sept",
    "numero-neuf": "Numero Neuf",
    "numero-dix": "Numero Dix",
    "numero-huit": "Numero Huit",
    "cyme": "Cyme",
    "beri": "Beri",
    "umi": "Umi",
    "tonca": "Tonca",
    "nodde": "Nodde",
    "mokki": "Mokki",
    "toni": "Toni",
}

IACUCCI_SIGNATURE_LABELS = {
    "ghibli": "Ghibli",
    "sorbetto": "Sorbetto",
}

MARNI_SIGNATURE_LABELS = {
    "museo": "Museo",
    "trunk": "Trunk",
}

ALL_SIGNATURE_LABELS = {**POLENE_SIGNATURE_LABELS, **IACUCCI_SIGNATURE_LABELS, **MARNI_SIGNATURE_LABELS}


@dataclass(slots=True)
class Listing:
    brand: str
    title: str
    price: int
    url: str
    site: str
    sold: bool = False
    metadata: dict | None = None
    image_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SoldStats:
    brand: str
    sold_median: float
    sold_avg: float
    sample_count: int
    popularity_color_hint: str
    popularity_color_hints: list[str]
    popularity_color_hint_top1: str
    popularity_color_hint_top2: str
    popularity_color_hint_top3: str
    popularity_color_bands: list[str]
    popularity_color_band_top1: str
    popularity_color_band_top2: str
    popularity_color_band_top3: str
    sold_titles: list[str]
    popularity_color_top1_count: int
    popularity_color_top1_ratio: float
    popularity_color_top2_count: int
    popularity_color_top2_ratio: float
    popularity_color_top3_count: int
    popularity_color_top3_ratio: float


@dataclass(slots=True)
class ListingProfile:
    category: str | None
    colors: list[str]
    color_bands: list[str]
    raw_color_text: str
    primary_color: str
    secondary_colors: list[str]
    primary_color_band: str
    secondary_color_bands: list[str]
    model_tokens: set[str]
    line_tokens: set[str]
    material_tokens: set[str]
    size_tokens: set[str]
    strict_signature: str


@dataclass(slots=True)
class MatchResult:
    estimated_price: float
    matched_keywords: list[str]
    note: str
    model_match: bool
    line_match: bool
    material_match: bool
    size_match: bool
    color_match: bool
    matched_sold_count: int
    model_signature: str
    sold_model_signature: str
    popularity_color_hint: str
    popularity_color_hints: list[str]
    popularity_color_hint_top1: str
    popularity_color_hint_top2: str
    popularity_color_hint_top3: str
    popularity_color_bands: list[str]
    popularity_color_band_top1: str
    popularity_color_band_top2: str
    popularity_color_band_top3: str
    strict_validation_note: str


@dataclass(slots=True)
class BrandAnalysisStats:
    primary_candidate_count: int = 0
    similar_sold_shortage_count: int = 0
    out_of_stock_excluded_count: int = 0
    non_main_product_excluded_count: int = 0
    model_mismatch_hold_or_skip_count: int = 0
    final_honmei_count: int = 0
    final_hold_count: int = 0
    site_excluded_count: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    site_final_candidate_count: dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass(slots=True)
class BrandAnalysisResult:
    rows: list[dict]
    stats: BrandAnalysisStats
    sold_stats: SoldStats | None


def is_brand_like_candidate(token: str) -> bool:
    normalized = normalize_text(token)
    if not normalized or len(normalized) < 3:
        return False
    if normalized in DISCOVERY_STOPWORDS:
        return False
    if detect_color(normalized) != "unknown":
        return False
    if contains_bag_keyword(normalized):
        return False
    if normalized.isdigit():
        return False
    if re.fullmatch(r"[a-z0-9]+", normalized):
        return len(normalized) >= 4 and not any(char.isdigit() for char in normalized)
    return bool(re.search(r"[ぁ-んァ-ヶー一-龠]", normalized))


def build_sold_stats(brand: str, sold_listings: Iterable[Listing]) -> SoldStats:
    sold_items = [item for item in sold_listings if is_target_category(item.title)]
    prices = [item.price for item in sold_items if item.price]
    titles = [item.title for item in sold_items if item.title]

    raw_top_colors = top_common_colors(titles, limit=3)
    top_colors = (raw_top_colors + ["unknown", "unknown", "unknown"])[:3]
    raw_top_bands = top_common_color_bands(titles, limit=3)
    top_bands = (raw_top_bands + ["unknown", "unknown", "unknown"])[:3]

    total_titles = len(titles) or 1
    color_item_counter: Counter[str] = Counter()
    for title in titles:
        for c in set(detect_colors(title)):
            color_item_counter[c] += 1

    def _count(color: str) -> int:
        return color_item_counter.get(color, 0) if color != "unknown" else 0

    def _ratio(color: str) -> float:
        return round(_count(color) / total_titles, 4) if color != "unknown" else 0.0

    return SoldStats(
        brand=brand,
        sold_median=safe_median(prices),
        sold_avg=safe_average(prices),
        sample_count=len(prices),
        popularity_color_hint=top_colors[0],
        popularity_color_hints=raw_top_colors,
        popularity_color_hint_top1=top_colors[0],
        popularity_color_hint_top2=top_colors[1],
        popularity_color_hint_top3=top_colors[2],
        popularity_color_bands=raw_top_bands,
        popularity_color_band_top1=top_bands[0],
        popularity_color_band_top2=top_bands[1],
        popularity_color_band_top3=top_bands[2],
        sold_titles=titles,
        popularity_color_top1_count=_count(top_colors[0]),
        popularity_color_top1_ratio=_ratio(top_colors[0]),
        popularity_color_top2_count=_count(top_colors[1]),
        popularity_color_top2_ratio=_ratio(top_colors[1]),
        popularity_color_top3_count=_count(top_colors[2]),
        popularity_color_top3_ratio=_ratio(top_colors[2]),
    )


def _extract_strict_signature(title: str, normalized_brand: str) -> str:
    if normalized_brand == "polene":
        return extract_polene_model(title)
    if normalized_brand == "iacucci":
        return extract_iacucci_model(title)
    if normalized_brand == "marni":
        return extract_marni_model(title)
    return ""


def build_profile(listing: Listing, brand: str) -> ListingProfile:
    normalized_brand = normalize_text(brand)
    strict_signature = _extract_strict_signature(listing.title, normalized_brand)
    color_features = extract_color_features(listing.title)
    brand_parts = {t for t in re.findall(r"[a-z0-9]+", normalized_brand) if len(t) >= 5}
    return ListingProfile(
        category=detect_target_category(listing.title),
        colors=list(color_features["detected_colors"]),
        color_bands=list(color_features["detected_color_bands"]),
        raw_color_text=str(color_features["raw_color_text"]),
        primary_color=str(color_features["primary_color"]),
        secondary_colors=list(color_features["secondary_colors"]),
        primary_color_band=str(color_features["primary_color_band"]),
        secondary_color_bands=list(color_features["secondary_color_bands"]),
        model_tokens=set(extract_model_tokens(listing.title)) - brand_parts,
        line_tokens=set(extract_line_tokens(listing.title, brand)),
        material_tokens=set(extract_material_tokens(listing.title)),
        size_tokens=set(extract_size_tokens(listing.title)),
        strict_signature=strict_signature,
    )


def _display_signature(signature: str) -> str:
    if not signature:
        return ""
    return ALL_SIGNATURE_LABELS.get(signature, signature.replace("-", " ").title())


def score_match(source: Listing, sold_item: Listing, brand: str) -> tuple[float, list[str], dict]:
    source_title = normalize_text(source.title)
    sold_title = normalize_text(sold_item.title)
    normalized_brand = normalize_text(brand)
    brand_variants = [normalized_brand] + [normalize_text(a) for a in BRAND_ALIASES.get(brand, [])]
    matched_keywords: list[str] = []

    source_ok = any(v in source_title for v in brand_variants)
    sold_ok = any(v in sold_title for v in brand_variants)
    if not source_ok or not sold_ok:
        return 0.0, matched_keywords, {}

    sold_brand_match = next(v for v in brand_variants if v in sold_title)
    source_profile = build_profile(source, brand)
    sold_profile = build_profile(sold_item, sold_brand_match)
    if not source_profile.category or not sold_profile.category or source_profile.category != sold_profile.category:
        return 0.0, matched_keywords, {}

    score = 10.0
    strict_notes: list[str] = []
    strict_brand = normalize_text(brand).upper() in {name.upper() for name in STRICT_MODEL_BRANDS}

    if strict_brand:
        if source_profile.strict_signature and sold_profile.strict_signature:
            if source_profile.strict_signature != sold_profile.strict_signature:
                return 0.0, matched_keywords, {}
            score += 50
            matched_keywords.append(source_profile.strict_signature)
            strict_notes.append(f"モデル系統一致={_display_signature(source_profile.strict_signature)}")
        elif source_profile.strict_signature:
            strict_notes.append(f"売り手候補モデル={_display_signature(source_profile.strict_signature)}")
        elif sold_profile.strict_signature:
            strict_notes.append(f"売り切れ候補モデル={_display_signature(sold_profile.strict_signature)}")

    model_overlap = source_profile.model_tokens & sold_profile.model_tokens
    if source_profile.model_tokens and sold_profile.model_tokens and not model_overlap and not strict_brand:
        return 0.0, matched_keywords, {}
    if model_overlap:
        score += 42
        matched_keywords.extend(sorted(model_overlap))

    line_overlap = source_profile.line_tokens & sold_profile.line_tokens
    if source_profile.line_tokens and sold_profile.line_tokens and not line_overlap and not model_overlap and not source_profile.strict_signature:
        return 0.0, matched_keywords, {}
    if line_overlap:
        score += min(24, len(line_overlap) * 8)
        matched_keywords.extend(sorted(line_overlap)[:4])

    material_overlap = source_profile.material_tokens & sold_profile.material_tokens
    if material_overlap:
        score += min(14, len(material_overlap) * 5)
        matched_keywords.extend(sorted(material_overlap))

    size_overlap = source_profile.size_tokens & sold_profile.size_tokens
    if source_profile.size_tokens and sold_profile.size_tokens and not size_overlap:
        return 0.0, matched_keywords, {}
    if size_overlap:
        score += min(12, len(size_overlap) * 6)
        matched_keywords.extend(sorted(size_overlap))

    color_overlap = set(source_profile.colors) & set(sold_profile.colors)
    if color_overlap:
        score += 8
        matched_keywords.extend(sorted(color_overlap))

    source_tokens = set(tokenize(source.title))
    sold_tokens = set(tokenize(sold_item.title))
    ignore_tokens = {normalized_brand, "new", "used", "中古", "レディース", "メンズ"}
    token_overlap = {token for token in (source_tokens & sold_tokens) if token not in ignore_tokens}
    if token_overlap:
        score += min(24, len(token_overlap) * 4)
        matched_keywords.extend(sorted(token_overlap)[:6])

    score += fuzz.token_set_ratio(source.title, sold_item.title) * 0.18
    return score, list(dict.fromkeys(matched_keywords)), {
        "source_profile": source_profile,
        "sold_profile": sold_profile,
        "strict_notes": strict_notes,
    }


def estimate_sale_price(source: Listing, sold_items: list[Listing], stats: SoldStats, brand: str) -> MatchResult:
    scored: list[tuple[float, Listing, list[str], dict]] = []
    for sold_item in sold_items:
        score, keywords, details = score_match(source, sold_item, brand)
        if score >= 35:
            scored.append((score, sold_item, keywords, details))

    empty_colors = ["unknown", "unknown", "unknown"]
    if not scored:
        return MatchResult(
            0.0,
            [],
            "類似売り切れ不足",
            False,
            False,
            False,
            False,
            False,
            0,
            "",
            "",
            "unknown",
            empty_colors,
            empty_colors[0],
            empty_colors[1],
            empty_colors[2],
            empty_colors,
            empty_colors[0],
            empty_colors[1],
            empty_colors[2],
            "",
        )

    scored.sort(key=lambda row: row[0], reverse=True)
    top_items = scored[:5]
    if len(top_items) < 3:
        return MatchResult(
            0.0,
            [],
            "類似売り切れ件数不足",
            False,
            False,
            False,
            False,
            False,
            len(top_items),
            "",
            "",
            "unknown",
            empty_colors,
            empty_colors[0],
            empty_colors[1],
            empty_colors[2],
            empty_colors,
            empty_colors[0],
            empty_colors[1],
            empty_colors[2],
            "",
        )

    estimated_price = safe_median(item.price for _, item, _, _ in top_items) or stats.sold_median
    merged_keywords: list[str] = []
    sold_model_signatures: list[str] = []
    sold_titles: list[str] = []
    model_match = False
    line_match = False
    material_match = False
    size_match = False
    color_match = False
    strict_notes: list[str] = []
    source_profile = build_profile(source, brand)

    for _, item, keywords, details in top_items:
        merged_keywords.extend(keywords or pick_representative_keywords(item.title, brand))
        sold_titles.append(item.title)
        sold_profile: ListingProfile = details["sold_profile"]
        if sold_profile.strict_signature:
            sold_model_signatures.append(sold_profile.strict_signature)
        if source_profile.model_tokens & sold_profile.model_tokens or (
            source_profile.strict_signature and source_profile.strict_signature == sold_profile.strict_signature
        ):
            model_match = True
        if source_profile.line_tokens & sold_profile.line_tokens or (
            source_profile.strict_signature and source_profile.strict_signature == sold_profile.strict_signature
        ):
            line_match = True
        if source_profile.material_tokens & sold_profile.material_tokens:
            material_match = True
        if source_profile.size_tokens & sold_profile.size_tokens:
            size_match = True
        if set(source_profile.colors) & set(sold_profile.colors):
            color_match = True
        strict_notes.extend(details["strict_notes"])

    source_signature = source_profile.strict_signature
    sold_signature = Counter(sold_model_signatures).most_common(1)[0][0] if sold_model_signatures else ""
    if source_signature and sold_signature == source_signature:
        model_match = True

    popularity_color_hints = top_common_colors(sold_titles, limit=3)
    popularity_color_hints = (popularity_color_hints + ["unknown", "unknown", "unknown"])[:3]
    popularity_color_bands = top_common_color_bands(sold_titles, limit=3)
    popularity_color_bands = (popularity_color_bands + ["unknown", "unknown", "unknown"])[:3]

    return MatchResult(
        estimated_price=estimated_price,
        matched_keywords=list(dict.fromkeys(merged_keywords))[:8],
        note=f"類似売り切れ{len(top_items)}件ベースで推定",
        model_match=model_match,
        line_match=line_match,
        material_match=material_match,
        size_match=size_match,
        color_match=color_match,
        matched_sold_count=len(top_items),
        model_signature=_display_signature(source_signature),
        sold_model_signature=_display_signature(sold_signature),
        popularity_color_hint=popularity_color_hints[0],
        popularity_color_hints=popularity_color_hints,
        popularity_color_hint_top1=popularity_color_hints[0],
        popularity_color_hint_top2=popularity_color_hints[1],
        popularity_color_hint_top3=popularity_color_hints[2],
        popularity_color_bands=popularity_color_bands,
        popularity_color_band_top1=popularity_color_bands[0],
        popularity_color_band_top2=popularity_color_bands[1],
        popularity_color_band_top3=popularity_color_bands[2],
        strict_validation_note=" / ".join(dict.fromkeys(strict_notes)),
    )


def classify_candidate_rank(row: dict) -> str:
    if row["review_required"]:
        return "hold"
    if not row["model_match"]:
        return "hold"
    # slow ブランドは color_alignment=strong でも review_required=True 扱い
    if row.get("sell_speed") == "slow":
        return "hold"
    # 仕入れ側にサイズ明記があるが売り切れ側にサイズ一致がない場合は strong を降格
    effective_alignment = row["color_alignment"]
    if row.get("source_has_size") and not row["size_match"]:
        effective_alignment = "neutral"  # パターンA: サイズ不明マッチ → strong 無効
    # top1 色一致（strong）のみ本命 — top2(near)以下・neutral・unknown は常に hold
    if effective_alignment == "strong":
        return "honmei"
    return "hold"


def analyze_brand(
    brand: str,
    sold_items: list[Listing],
    source_items: list[Listing],
    config: ScraperConfig,
    auto_discovered_brand: bool = False,
    discovery_note: str = "",
) -> BrandAnalysisResult:
    filtered_sold_items = [item for item in sold_items if is_target_category(item.title)]
    if not filtered_sold_items:
        return BrandAnalysisResult([], BrandAnalysisStats(), None)

    sold_stats = build_sold_stats(brand, filtered_sold_items)
    if sold_stats.sample_count < config.min_mercari_sample_count:
        return BrandAnalysisResult([], BrandAnalysisStats(), sold_stats)

    stats = BrandAnalysisStats()
    rows: list[dict] = []
    sell_speed = BRAND_SELL_SPEED.get(brand, "medium")

    for source in source_items:
        site = source.site
        if site not in SOURCE_SITES:
            continue

        availability_status = (source.metadata or {}).get("availability_status", "available")
        if is_unavailable_status(availability_status):
            stats.out_of_stock_excluded_count += 1
            stats.site_excluded_count[site] += 1
            continue

        if not is_target_category(source.title) or contains_excluded_candidate_term(source.title) or not is_main_product(source.title):
            stats.non_main_product_excluded_count += 1
            stats.site_excluded_count[site] += 1
            continue

        normalized_brand_upper = normalize_text(brand).upper()
        if normalized_brand_upper not in {normalize_text(b).upper() for b in NO_MODEL_REQUIRED_BRANDS}:
            source_profile_check = build_profile(source, brand)
            if not source_profile_check.model_tokens and not source_profile_check.strict_signature:
                logger.info("[analyzer] モデル名なしで除外: %s", source.title)
                stats.non_main_product_excluded_count += 1
                stats.site_excluded_count[site] += 1
                continue

        brand_max_normal = BRAND_MAX_PRICE.get(brand, config.max_source_price)
        brand_max_review = BRAND_MAX_PRICE_REVIEW.get(brand, config.max_source_price)
        if source.price is None or source.price > brand_max_review:
            stats.site_excluded_count[site] += 1
            continue
        price_review_required = source.price > brand_max_normal

        match_result = estimate_sale_price(source, filtered_sold_items, sold_stats, brand)
        if match_result.estimated_price <= 0 or match_result.matched_sold_count < 3:
            stats.similar_sold_shortage_count += 1
            stats.site_excluded_count[site] += 1
            continue

        shipping = guess_shipping_fee(source.title)
        fee = round(match_result.estimated_price * config.mercari_fee_rate)
        gross_profit = match_result.estimated_price - fee - shipping - source.price
        profit_rate = gross_profit / source.price if source.price else -1
        if gross_profit < config.min_profit_amount or profit_rate < config.min_profit_rate:
            stats.site_excluded_count[site] += 1
            continue

        sold_count_review_required = match_result.matched_sold_count < 5
        review_required = sold_stats.sample_count < 8 or price_review_required or sold_count_review_required
        row_note_parts = [match_result.note]
        if sold_stats.sample_count < 8:
            row_note_parts.append(f"要目視確認(mercari_sample_count={sold_stats.sample_count})")
        if sold_count_review_required:
            row_note_parts.append(f"要目視確認(matched_sold_count={match_result.matched_sold_count})")
        if price_review_required:
            row_note_parts.append(f"価格検討枠(仕入¥{source.price:,} > 通常上限¥{brand_max_normal:,})")
        if match_result.strict_validation_note:
            row_note_parts.append(match_result.strict_validation_note)
        if discovery_note:
            row_note_parts.append(discovery_note)

        source_color_features = extract_color_features(source.title)
        popularity_color_hints = match_result.popularity_color_hints or sold_stats.popularity_color_hints
        popularity_color_bands = match_result.popularity_color_bands or sold_stats.popularity_color_bands
        color_alignment, color_reason = evaluate_color_alignment(
            source_color_features["detected_colors"],
            source_color_features["detected_color_bands"],
            popularity_color_hints,
            popularity_color_bands,
        )
        row_note_parts.append(
            f"売れ筋上位色帯={','.join(popularity_color_bands[:3]) or 'unknown'} / "
            f"商品配色={','.join(source_color_features['detected_color_bands']) or 'unknown'} / {color_reason}"
        )

        row = {
            "brand": brand,
            "auto_discovered_brand": auto_discovered_brand,
            "source_site": site,
            "source_title": source.title,
            "source_price": source.price,
            "source_url": source.url,
            "availability_status": availability_status,
            "mercari_sold_median": round(sold_stats.sold_median),
            "mercari_sold_avg": round(sold_stats.sold_avg),
            "mercari_sample_count": sold_stats.sample_count,
            "matched_sold_count": match_result.matched_sold_count,
            "estimated_sale_price": round(match_result.estimated_price),
            "platform_fee": fee,
            "estimated_shipping": shipping,
            "gross_profit": round(gross_profit),
            "profit_rate": round(profit_rate, 4),
            "target_category": detect_target_category(source.title) or "unknown",
            "model_match": match_result.model_match,
            "model_signature": match_result.model_signature,
            "sold_model_signature": match_result.sold_model_signature,
            "line_match": match_result.line_match,
            "material_match": match_result.material_match,
            "size_match": match_result.size_match,
            "source_has_size": bool(extract_size_tokens(source.title)),
            "is_main_item": True,
            "raw_color_text": source_color_features["raw_color_text"],
            "primary_color": source_color_features["primary_color"],
            "secondary_colors": ",".join(source_color_features["secondary_colors"]),
            "detected_colors": ",".join(source_color_features["detected_colors"]),
            "color_detected": source_color_features["color_detected"],
            "primary_color_band": source_color_features["primary_color_band"],
            "secondary_color_bands": ",".join(source_color_features["secondary_color_bands"]),
            "detected_color_bands": ",".join(source_color_features["detected_color_bands"]),
            "popularity_color_hint": match_result.popularity_color_hint or sold_stats.popularity_color_hint,
            "popularity_color_hint_top1": match_result.popularity_color_hint_top1 or sold_stats.popularity_color_hint_top1,
            "popularity_color_hint_top2": match_result.popularity_color_hint_top2 or sold_stats.popularity_color_hint_top2,
            "popularity_color_hints": ",".join(popularity_color_hints),
            "popularity_color_band_top1": match_result.popularity_color_band_top1 or sold_stats.popularity_color_band_top1,
            "popularity_color_band_top2": match_result.popularity_color_band_top2 or sold_stats.popularity_color_band_top2,
            "popularity_color_bands": ",".join(popularity_color_bands),
            "color_match": match_result.color_match,
            "color_alignment": color_alignment,
            "matched_keywords": ",".join(match_result.matched_keywords),
            "review_required": review_required,
            "sell_speed": sell_speed,
            "popularity_color_top1_count": sold_stats.popularity_color_top1_count,
            "popularity_color_top1_ratio": sold_stats.popularity_color_top1_ratio,
            "popularity_color_top2_count": sold_stats.popularity_color_top2_count,
            "popularity_color_top2_ratio": sold_stats.popularity_color_top2_ratio,
            "popularity_color_top3_count": sold_stats.popularity_color_top3_count,
            "popularity_color_top3_ratio": sold_stats.popularity_color_top3_ratio,
            "note": " / ".join(part for part in row_note_parts if part),
        }
        # ── 状態ランクフィルター（condition_filter） ──
        source_title_text = str(source.title or "")
        source_site_name  = str(getattr(source, "site_name", "") or "")

        # サイト別ランク正規化（ラベル直接マッチ）
        cond_rank = normalize_condition(source_site_name, source_title_text)
        # ラベルが取れなければ説明文から推定
        if not cond_rank:
            cond_rank = extract_condition_from_text(source_site_name, source_title_text)

        row["condition_rank"] = cond_rank or ""

        # 危険語チェック
        danger_level = check_description_words(source_title_text)
        row["danger_word"] = source_title_text if danger_level != "allow" else ""

        # 状態ランクによる除外・保留
        if cond_rank in REJECT_RANKS:
            row["review_required"] = True
            row["note"] = f"状態除外({cond_rank}) / " + row.get("note", "")
        elif cond_rank in REVIEW_RANKS:
            row["review_required"] = True
            row["note"] = f"状態保留({cond_rank}) / " + row.get("note", "")

        # 危険語による除外
        if danger_level == "reject":
            row["review_required"] = True
            row["note"] = f"危険語(reject) / " + row.get("note", "")
        elif danger_level == "review":
            row["review_required"] = True
            row["note"] = f"要確認語(review) / " + row.get("note", "")
        # ── ここまで condition_filter ──

        row["candidate_rank"] = classify_candidate_rank(row)

        stats.primary_candidate_count += 1
        if row["candidate_rank"] == "hold" and not row["model_match"]:
            stats.model_mismatch_hold_or_skip_count += 1
        if row["gross_profit"] >= config.final_output_min_profit:
            stats.site_final_candidate_count[site] += 1
            if row["candidate_rank"] == "honmei":
                stats.final_honmei_count += 1
            else:
                stats.final_hold_count += 1

        rows.append(row)

    return BrandAnalysisResult(rows, stats, sold_stats)


def discover_additional_brands(
    prioritized_brands: list[str],
    sold_items_by_brand: dict[str, list[Listing]],
    limit: int,
) -> list[dict]:
    discovered: list[dict] = []
    prioritized_normalized = {normalize_text(brand) for brand in prioritized_brands}
    candidate_counter: dict[str, Counter] = defaultdict(Counter)

    for items in sold_items_by_brand.values():
        for item in items:
            tokens = tokenize(item.title)
            has_bag_keyword = contains_bag_keyword(item.title)
            for token in tokens[:8]:
                if not is_brand_like_candidate(token):
                    continue
                if token in prioritized_normalized or token in AMBIGUOUS_BRANDS:
                    continue
                candidate_counter[token]["total_hits"] += 1
                if has_bag_keyword:
                    candidate_counter[token]["bag_hits"] += 1

    ranked: list[tuple[str, int, float]] = []
    for candidate, counter in candidate_counter.items():
        total_hits = counter["total_hits"]
        bag_hits = counter["bag_hits"]
        if total_hits < 3:
            continue
        bag_ratio = bag_hits / total_hits if total_hits else 0.0
        if bag_ratio < 0.7:
            continue
        ranked.append((candidate, total_hits, bag_ratio))

    ranked.sort(key=lambda row: (row[1], row[2], row[0]), reverse=True)
    for candidate, total_hits, bag_ratio in ranked[:limit]:
        discovered.append(
            {
                "brand": candidate.upper() if candidate.isascii() else candidate,
                "auto_discovered_brand": True,
                "note": f"auto discovery: 売れ筋件数={total_hits}, バッグ比率={bag_ratio:.0%}",
            }
        )
    return discovered


def _signed_yen(value: int) -> str:
    if value >= 0:
        return f"+{format_yen(value)}"
    return f"-{format_yen(abs(value))}"


def create_summary_lines(
    df: pd.DataFrame,
    analyzed_brand_count: int,
    auto_brand_count: int,
    output_path: str,
) -> str:
    if df.empty:
        return (
            "利益候補は見つかりませんでした。\n"
            "======== 集計 ========\n"
            f"解析ブランド数: {analyzed_brand_count}\n"
            "利益候補ありブランド数: 0\n"
            f"自動追加ブランド数: {auto_brand_count}\n"
            "利益候補総数: 0件\n"
            "想定利益合計: +¥0\n"
            "最大利益候補: なし\n"
            f"CSV保存先: {output_path}"
        )

    lines: list[str] = []
    for brand, group in df.groupby("brand", sort=False):
        sorted_group = group.sort_values(["gross_profit", "profit_rate"], ascending=[False, False])
        max_row = sorted_group.iloc[0]
        color_parts: list[str] = []
        for i in [1, 2, 3]:
            color = max_row.get(f"popularity_color_hint_top{i}", "unknown")
            count = int(max_row.get(f"popularity_color_top{i}_count", 0))
            ratio = float(max_row.get(f"popularity_color_top{i}_ratio", 0.0))
            if color and color != "unknown" and count > 0:
                color_parts.append(f"{color} {count}件({ratio:.0%})")
        color_dist_str = " / ".join(color_parts)
        lines.append(f"[{brand}]")
        lines.append(
            f"{brand} は {format_yen(int(group['mercari_sold_median'].median()))}売り切れ相場、"
            f"売り切れ{int(group['mercari_sample_count'].max())}件、利益候補{len(group)}件、"
            f"最大利益{_signed_yen(int(max_row['gross_profit']))} でした。"
            + (f" 人気色: {color_dist_str}" if color_dist_str else "")
        )
        lines.append("")
    lines.extend(
        [
            "======== 集計 ========",
            f"解析ブランド数: {analyzed_brand_count}",
            f"利益候補ありブランド数: {df['brand'].nunique()}",
            f"自動追加ブランド数: {auto_brand_count}",
            f"利益候補総数: {len(df)}件",
            f"想定利益合計: {_signed_yen(int(df['gross_profit'].sum()))}",
            f"最大利益候補: {df.sort_values(['gross_profit', 'profit_rate'], ascending=[False, False]).iloc[0]['source_title']}",
            f"CSV保存先: {output_path}",
        ]
    )
    return "\n".join(lines)


def save_results(rows: list[dict], output_path: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "brand",
                "auto_discovered_brand",
                "source_site",
                "source_title",
                "source_price",
                "source_url",
                "availability_status",
                "mercari_sold_median",
                "mercari_sold_avg",
                "mercari_sample_count",
                "matched_sold_count",
                "estimated_sale_price",
                "platform_fee",
                "estimated_shipping",
                "gross_profit",
                "profit_rate",
                "target_category",
                "model_match",
                "model_signature",
                "sold_model_signature",
                "line_match",
                "material_match",
                "size_match",
                "source_has_size",
                "is_main_item",
                "raw_color_text",
                "primary_color",
                "secondary_colors",
                "detected_colors",
                "color_detected",
                "primary_color_band",
                "secondary_color_bands",
                "detected_color_bands",
                "popularity_color_hint",
                "popularity_color_hint_top1",
                "popularity_color_hint_top2",
                "popularity_color_hints",
                "popularity_color_band_top1",
                "popularity_color_band_top2",
                "popularity_color_bands",
                "color_match",
                "color_alignment",
                "matched_keywords",
                "review_required",
                "sell_speed",
                "popularity_color_top1_count",
                "popularity_color_top1_ratio",
                "popularity_color_top2_count",
                "popularity_color_top2_ratio",
                "popularity_color_top3_count",
                "popularity_color_top3_ratio",
                "candidate_rank",
                "note",
            ]
        )
    else:
        df = df.sort_values(["gross_profit", "profit_rate"], ascending=[False, False]).reset_index(drop=True)
        # candidate_rank を視認しやすい先頭寄りに並び替え
        priority_cols = ["candidate_rank", "brand", "source_site", "source_title", "source_price", "gross_profit", "profit_rate"]
        other_cols = [c for c in df.columns if c not in priority_cols]
        df = df[priority_cols + other_cols]
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return df
