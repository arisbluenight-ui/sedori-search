from __future__ import annotations

import html
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime
from statistics import median
from typing import Iterable
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from config import (
    BAG_KEYWORDS,
    COLOR_RULES,
    EXCLUDED_CANDIDATE_TERMS,
    MATERIAL_KEYWORDS,
    NON_MAIN_PRODUCT_TERMS,
    POLENE_MODEL_PATTERNS,
    RAW_COLOR_VARIANTS,
    SIZE_KEYWORDS,
    TARGET_CATEGORY_KEYWORDS,
    UNAVAILABLE_STATUSES,
)


SEPARATOR_PATTERN = re.compile(r"[／/｜|・×xX,+]+")
JUNK_TITLE_CHARS = {
    "\u3013",  # 〓
    "\ufffd",  # replacement char
}


EXTRA_EXCLUDED_BAG_WORDS = {
    "エコバッグ",
    "パッカブル",
    "折りたたみ",
    "ショッピングバッグ",
    "shopper",
    "grocery",
}


UNAVAILABLE_STATUS_PATTERNS = [
    ("SOLD OUT", ["sold out"]),
    ("在庫なし", ["在庫なし"]),
    ("お取り寄せ中", ["お取り寄せ中", "取り寄せ中", "取寄keep", "取寄"]),
    ("入荷待ち", ["入荷待ち"]),
    ("売り切れ", ["売り切れ"]),
]

NEUTRAL_PRIORITY_COLORS = {"black", "brown", "white", "beige"}
FLASHY_PRIORITY_COLORS = {"red", "blue", "green", "yellow", "pink"}
COLOR_BAND_MAP = {
    "black": "black",
    "brown": "brown",
    "white": "white-beige",
    "beige": "white-beige",
    "red": "red-pink",
    "pink": "red-pink",
    "blue": "blue-navy",
    "green": "green",
    "yellow": "yellow",
    "metallic": "metallic",
}
NEUTRAL_COLOR_BANDS = {"black", "brown", "white-beige", "metallic"}
FLASHY_COLOR_BANDS = {"red-pink", "blue-navy", "green", "yellow"}


def ensure_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = html.unescape(normalized)
    normalized = normalized.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def clean_title_text(text: str | None) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(text or ""))
    for char in JUNK_TITLE_CHARS:
        value = value.replace(char, " ")
    value = value.replace("\u00a0", " ")
    value = value.replace("◆", " ")
    value = value.replace("☆", " ")
    value = value.replace("★", " ")
    value = re.sub(r"[【】\[\]{}<>]+", " ", value)
    value = re.sub(r"[!！?？]{2,}", " ", value)
    value = re.sub(r"[・]{2,}", "・", value)
    value = re.sub(r"[/]{2,}", "/", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" /・-")


def tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    return re.findall(r"[a-zà-ÿ0-9]+|[ぁ-んァ-ヶー一-龠]+", text)


def extract_price(text: str | None) -> int | None:
    if not text:
        return None
    compact = normalize_text(text).replace(",", "")
    match = re.search(r"(\d{2,})", compact)
    if not match:
        return None
    return int(match.group(1))


def format_yen(value: int | float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}¥{abs(int(round(value))):,}"


def encode_query(query: str) -> str:
    return quote_plus(query)


def _color_variant_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, variants in COLOR_RULES.items():
        for variant in variants:
            mapping[normalize_text(variant)] = canonical
    return mapping


COLOR_VARIANT_MAP = _color_variant_map()


def extract_raw_color_text(text: str) -> str:
    normalized = normalize_text(text)
    found: list[tuple[int, str]] = []
    for variant in RAW_COLOR_VARIANTS:
        variant_key = normalize_text(variant)
        if not variant_key:
            continue
        index = normalized.find(variant_key)
        if index >= 0:
            found.append((index, clean_title_text(variant)))
    if not found:
        return ""

    found.sort(key=lambda item: item[0])
    raw_values: list[str] = []
    for _, value in found:
        if value not in raw_values:
            raw_values.append(value)
    return "/".join(raw_values)


def detect_colors(title: str) -> list[str]:
    normalized = normalize_text(title)
    matches: list[tuple[int, str]] = []
    for variant_key, canonical in COLOR_VARIANT_MAP.items():
        if not variant_key:
            continue
        index = normalized.find(variant_key)
        if index >= 0:
            matches.append((index, canonical))
    if not matches:
        return []

    matches.sort(key=lambda item: item[0])
    detected: list[str] = []
    for _, canonical in matches:
        if canonical not in detected:
            detected.append(canonical)
    return detected


def detect_color(title: str) -> str:
    detected = detect_colors(title)
    if not detected:
        return "unknown"
    return "/".join(detected)


def classify_color_priority(detected_colors: Iterable[str], popularity_color_hint: str) -> str:
    colors = [normalize_text(color) for color in detected_colors if color]
    colors = [color for color in colors if color and color != "unknown"]
    popularity = normalize_text(popularity_color_hint or "")

    if popularity and popularity in colors:
        return "popularity_match"
    if any(color in NEUTRAL_PRIORITY_COLORS for color in colors):
        return "neutral_mismatch"
    if any(color in FLASHY_PRIORITY_COLORS for color in colors):
        return "flashy_mismatch"
    return "unknown"


def color_bands_from_colors(colors: Iterable[str]) -> list[str]:
    bands: list[str] = []
    for color in colors:
        band = COLOR_BAND_MAP.get(normalize_text(color), "unknown")
        if band != "unknown" and band not in bands:
            bands.append(band)
    return bands


def extract_color_features(text: str) -> dict[str, object]:
    colors = detect_colors(text)
    bands = color_bands_from_colors(colors)
    primary_color = colors[0] if colors else "unknown"
    primary_color_band = bands[0] if bands else "unknown"
    secondary_colors = colors[1:]
    secondary_color_bands = bands[1:]
    return {
        "raw_color_text": extract_raw_color_text(text),
        "primary_color": primary_color,
        "secondary_colors": secondary_colors,
        "detected_colors": colors,
        "color_detected": "/".join(colors) if colors else "unknown",
        "primary_color_band": primary_color_band,
        "secondary_color_bands": secondary_color_bands,
        "detected_color_bands": bands,
    }


def top_common_colors(titles: Iterable[str], limit: int = 3) -> list[str]:
    counter: Counter[str] = Counter()
    for title in titles:
        for color in detect_colors(title):
            counter[color] += 1
    return [color for color, _ in counter.most_common(limit)]


def top_common_color_bands(titles: Iterable[str], limit: int = 3) -> list[str]:
    counter: Counter[str] = Counter()
    for title in titles:
        for band in color_bands_from_colors(detect_colors(title)):
            counter[band] += 1
    return [band for band, _ in counter.most_common(limit)]


def evaluate_color_alignment(
    detected_colors: Iterable[str],
    detected_bands: Iterable[str],
    popularity_colors: Iterable[str],
    popularity_bands: Iterable[str],
) -> tuple[str, str]:
    detected_color_list = [normalize_text(color) for color in detected_colors if color]
    detected_band_list = [normalize_text(band) for band in detected_bands if band]
    popularity_color_list = [normalize_text(color) for color in popularity_colors if color and color != "unknown"]
    popularity_band_list = [normalize_text(band) for band in popularity_bands if band and band != "unknown"]

    top1_color = popularity_color_list[0] if popularity_color_list else None
    top1_band = popularity_band_list[0] if popularity_band_list else None
    top2_color = popularity_color_list[1] if len(popularity_color_list) > 1 else None
    top2_band = popularity_band_list[1] if len(popularity_band_list) > 1 else None

    # Top1 exact color or band match → strong
    if top1_color and top1_color in detected_color_list:
        return "strong", "売れ筋1位色と一致"
    if top1_band and top1_band in detected_band_list:
        return "strong", "売れ筋1位色帯と一致"

    # Top2 only match → near (保留)
    if top2_color and top2_color in detected_color_list:
        return "near", "売れ筋2位色と一致"
    if top2_band and top2_band in detected_band_list:
        return "near", "売れ筋2位色帯と一致"

    if any(band in NEUTRAL_COLOR_BANDS for band in detected_band_list):
        return "neutral", "人気色不一致だが落ち着いた定番配色"
    if detected_band_list and all(band in FLASHY_COLOR_BANDS for band in detected_band_list):
        return "flashy", "人気色不一致で派手色主体"
    return "unknown", "色帯一致は弱いが総合評価対象"


def detect_availability_status(text: str | None) -> str:
    normalized = normalize_text(text or "")
    if not normalized:
        return "available"
    for status, patterns in UNAVAILABLE_STATUS_PATTERNS:
        if any(normalize_text(pattern) in normalized for pattern in patterns):
            return status
    return "available"


def is_unavailable_status(status: str | None) -> bool:
    return (status or "").strip() in UNAVAILABLE_STATUSES


def guess_shipping_fee(title: str) -> int:
    normalized = normalize_text(title)
    small_keywords = ["財布", "ウォレット", "card case", "カードケース", "coin case", "コインケース", "名刺入れ"]
    bag_keywords = ["ハンドバッグ", "ショルダーバッグ", "トートバッグ", "バッグ", "bag"]
    large_keywords = ["リュック", "バックパック", "backpack", "大型バッグ"]

    if any(normalize_text(keyword) in normalized for keyword in small_keywords):
        return 210
    if any(normalize_text(keyword) in normalized for keyword in large_keywords):
        return 850
    if any(normalize_text(keyword) in normalized for keyword in bag_keywords):
        return 750
    return 520


def safe_median(values: Iterable[int | float]) -> float:
    clean = [float(v) for v in values if v is not None]
    return median(clean) if clean else 0.0


def safe_average(values: Iterable[int | float]) -> float:
    clean = [float(v) for v in values if v is not None]
    return sum(clean) / len(clean) if clean else 0.0


def most_common_color(titles: Iterable[str]) -> str:
    colors = top_common_colors(titles, limit=1)
    if not colors:
        return "unknown"
    return colors[0]


def contains_bag_keyword(text: str) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(keyword) in normalized for keyword in BAG_KEYWORDS)


def detect_target_category(title: str) -> str | None:
    normalized = normalize_text(title)
    for category, keywords in TARGET_CATEGORY_KEYWORDS.items():
        if any(normalize_text(keyword) in normalized for keyword in keywords):
            return category
    return None


def is_target_category(title: str) -> bool:
    return detect_target_category(title) is not None


def contains_excluded_candidate_term(title: str) -> bool:
    normalized = normalize_text(title)
    return any(normalize_text(term) in normalized for term in (set(EXCLUDED_CANDIDATE_TERMS) | EXTRA_EXCLUDED_BAG_WORDS))


def is_main_product(title: str) -> bool:
    normalized = normalize_text(title)
    if contains_excluded_candidate_term(title):
        return False
    return not any(normalize_text(term) in normalized for term in (set(NON_MAIN_PRODUCT_TERMS) | EXTRA_EXCLUDED_BAG_WORDS))


def title_similarity_tokens(left: str, right: str) -> set[str]:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    return left_tokens & right_tokens


def pick_representative_keywords(title: str, brand: str) -> list[str]:
    tokens = [token for token in tokenize(title) if token != normalize_text(brand)]
    filtered: list[str] = []
    for token in tokens:
        if len(token) >= 2 and token not in filtered:
            filtered.append(token)
    return filtered[:8]


def extract_model_tokens(text: str) -> list[str]:
    clean = clean_title_text(text)
    candidates = re.findall(r"[A-Za-z]{1,6}\d{2,}|\d{3,}[A-Za-z]{0,4}|[A-Za-z0-9]{5,}", clean)
    deduped: list[str] = []
    for candidate in candidates:
        token = candidate.lower()
        if token not in deduped:
            deduped.append(token)
    return deduped[:8]


def extract_material_tokens(text: str) -> list[str]:
    normalized = normalize_text(text)
    materials: list[str] = []
    for keyword in MATERIAL_KEYWORDS:
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword in normalized and normalized_keyword not in materials:
            materials.append(normalized_keyword)
    return materials


def extract_size_tokens(text: str) -> list[str]:
    normalized = normalize_text(text)
    size_patterns = [
        r"\b\d{2,3}\s?cm\b",
        r"\b\d{1,2}\s?(?:インチ|inch|in)\b",
        r"\b(?:mini|small|medium|large|big|pm|mm|gm)\b",
        r"(?:ミニ|スモール|ミディアム|ラージ|ビッグ)",
    ]
    tokens: list[str] = []
    for pattern in size_patterns:
        for match in re.findall(pattern, normalized):
            if match not in tokens:
                tokens.append(match)
    for keyword in SIZE_KEYWORDS:
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword in normalized and normalized_keyword not in tokens:
            tokens.append(normalized_keyword)
    return tokens[:8]


def extract_line_tokens(text: str, brand: str) -> list[str]:
    normalized_brand = normalize_text(brand)
    tokens = tokenize(text)
    excluded = {normalized_brand}
    excluded.update(normalize_text(keyword) for keyword in BAG_KEYWORDS)
    excluded.update(normalize_text(keyword) for keyword in MATERIAL_KEYWORDS)
    line_tokens: list[str] = []
    for token in tokens:
        if token in excluded:
            continue
        if len(token) < 3:
            continue
        if token.isdigit():
            continue
        if detect_color(token) != "unknown":
            continue
        if token not in line_tokens:
            line_tokens.append(token)
    return line_tokens[:8]


def extract_polene_model(text: str) -> str:
    normalized = normalize_text(clean_title_text(text))
    normalized = normalized.replace("num ro", "numero").replace("num ero", "numero").replace("num?ro", "numero")
    normalized = re.sub(r"num[^a-z0-9ぁ-んァ-ヶー一-龠]{0,2}ro", "numero", normalized)
    for canonical, variants in POLENE_MODEL_PATTERNS.items():
        for variant in variants:
            if normalize_text(variant) in normalized:
                return canonical
    return ""


def chunked(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[index:index + size] for index in range(0, len(items), size)]


def build_output_csv_path(output_dir, brands: list[str], now: datetime | None = None):
    current = now or datetime.now(ZoneInfo("Asia/Tokyo"))
    timestamp = current.strftime("%Y%m%d_%H%M%S")
    if brands:
        normalized_brands = [normalize_text(brand).replace(" ", "-") for brand in brands[:5]]
        brand_slug = "_".join(
            re.sub(r"[^a-z0-9ぁ-んァ-ヶー一-龠_-]+", "", brand) or "brand"
            for brand in normalized_brands
        )
    else:
        brand_slug = "all-brands"
    filename = f"profitable_items_{timestamp}_{brand_slug}.csv"
    return output_dir / filename
