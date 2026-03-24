from __future__ import annotations

import re
import unicodedata
from typing import Optional, Tuple

# ============================================================
# 内部共通ランク定義
# ============================================================
# SS: 新品級
# S : 未使用〜新品同様
# A : 使用感かなり少ない
# AB: 軽い使用感
# B : 一般中古
# BC: 使用感強め
# C : ダメージあり
# D : 難あり
# E : ジャンク寄り

CONDITION_RANK_ORDER = ["SS", "S", "A", "AB", "B", "BC", "C", "D", "E"]

# ============================================================
# サイト別 → 内部ランク マッピング
# ============================================================
SITE_CONDITION_MAP = {
    # モール系は店ごとの差が大きいため、基本は説明文優先
    "RAKUTEN": {},
    "YAHOO": {},

    "RAGTAG": {
        "新品同様": "S",
        "A": "A",
        "B": "B",
        "C": "C",
        "D": "D",
    },

    "ALLU": {
        "未使用": "S",
        "S": "A",   # 初期運用では保守的にA扱い
        "A": "A",
        "B": "B",
        "C": "C",
    },

    "RECLO": {
        "未使用": "S",
        "未使用に近い": "S",
        "良い": "A",
        "比較的良い": "AB",
        "やや傷あり": "B",
        "傷・汚れあり": "C",
    },

    "KOMEHYO": {
        "新品": "SS",
        "未使用品": "S",
        "中古品S": "A",   # 高評価だが初期運用では保守的にA扱い
        "中古品A": "A",
        "中古品B": "B",
        "中古品C": "C",
    },

    "VECTOR_PARK": {
        "新品・未使用": "SS",
        "未使用に近い": "S",
        "目立った傷や汚れなし": "A",
        "やや傷や汚れあり": "B",
        "傷や汚れあり": "C",
        "全体的に状態が悪い": "D",
    },

    "TREFAC": {
        "新品・未使用": "SS",
        "未使用に近い": "S",
        "A": "A",
        "B": "B",
        "C": "C",
        "D": "D",
    },

    "REHELLO": {
        "新品・未使用": "SS",
        "未使用に近い": "S",
        "良好": "A",
        "やや使用感": "B",
        "使用感あり": "BC",
        "傷汚れあり": "C",
    },

    # 現在は実質除外
    # "BRANDOFF": {},
    # "BRANDEAR": {},
}

# ============================================================
# 初期運用 許可ライン
# ============================================================
ALLOWED_RANKS = {"SS", "S", "A", "AB", "B"}
REVIEW_RANKS  = {"BC"}
REJECT_RANKS  = {"C", "D", "E"}

# ============================================================
# 危険語辞書
# ============================================================
DANGER_WORDS_REJECT = [
    "破れ", "剥がれ", "ベタつき",
    "壊れ", "欠損", "ジャンク", "難あり", "修理必要",
    "要補修", "使用不可", "部品欠品", "べたつき",
    "カビ", "臭い", "においあり", "並行輸入品",
]

DANGER_WORDS_REVIEW = [
    "スレ", "汚れ", "キズ", "角スレ", "型崩れ",
    "変色", "ヤケ", "におい", "内側汚れ", "金具キズ",
    "持ち手使用感", "付属品なし", "保存袋なし", "箱なし",
    "比較的良い", "使用可能", "まだまだ使える",
    "一般的な使用感", "使用感あり", "若干のダメージ",
    "経年感", "現状渡し", "ひび", "裂け",
]

# ============================================================
# モデル特定性チェック
# ============================================================
MODEL_SPECIFICITY_REQUIRED = [
    "model_name",
    "item_number",
    "line_name",
    "size",
]

STRICT_MODEL_CHECK_BRANDS = {
    "LOEWE", "PRADA", "GUCCI", "CELINE",
    "FENDI", "BURBERRY", "MIU MIU", "GIVENCHY",
}

# ============================================================
# 内部ユーティリティ
# ============================================================

def _normalize_text(text: str) -> str:
    """NFKC正規化 + 全角スペースを半角に統一して返す。"""
    return unicodedata.normalize("NFKC", text).replace("\u3000", " ").strip()


def _normalize_site(site: str) -> str:
    """scraper.site_name を SITE_CONDITION_MAP のキーに正規化する。"""
    site = _normalize_text(site).upper()

    aliases = {
        "楽天市場": "RAKUTEN",
        "RAKUTEN": "RAKUTEN",
        "RAKUTEN ICHIBA": "RAKUTEN",

        "YAHOOショッピング": "YAHOO",
        "YAHOO SHOPPING": "YAHOO",
        "YAHOO": "YAHOO",

        "RAGTAG": "RAGTAG",
        "ALLU": "ALLU",
        "RECLO": "RECLO",
        "KOMEHYO": "KOMEHYO",

        "VECTOR_PARK": "VECTOR_PARK",
        "ベクトルパーク": "VECTOR_PARK",

        "TREFAC": "TREFAC",
        "トレファクファッション": "TREFAC",

        "REHELLO": "REHELLO",
        "REHELLO BY BOOKOFF": "REHELLO",

        # 現在は実質除外
        "BRAND OFF": "BRANDOFF",
        "BRANDOFF": "BRANDOFF",
        "BRANDEAR": "BRANDEAR",
        "ブランディア": "BRANDEAR",
    }

    return aliases.get(site, site)


# ============================================================
# 公開 API
# ============================================================

def normalize_condition(site: str, raw: str) -> str | None:
    """サイト固有のコンディション表記を内部ランクに変換する。

    未登録サイト・未定義ラベルは None を返す。
    """
    key = _normalize_site(site)
    mapping = SITE_CONDITION_MAP.get(key, {})
    return mapping.get(raw.strip())


def rank_index(rank: str) -> int:
    """ランクの優劣インデックスを返す（小さい = 上質）。

    未知のランクは末尾 (len(CONDITION_RANK_ORDER)) として扱う。
    """
    try:
        return CONDITION_RANK_ORDER.index(rank)
    except ValueError:
        return len(CONDITION_RANK_ORDER)


def classify_by_rank(rank: str | None) -> str:
    """内部ランクから allow / review / reject / unknown を返す。"""
    if rank is None:
        return "unknown"
    if rank in ALLOWED_RANKS:
        return "allow"
    if rank in REVIEW_RANKS:
        return "review"
    if rank in REJECT_RANKS:
        return "reject"
    return "unknown"


def check_description_words(text: str) -> str:
    """説明文の危険語チェック。

    Returns:
        "reject" → DANGER_WORDS_REJECT に該当
        "review" → DANGER_WORDS_REVIEW に該当
        "allow"  → 該当なし
    """
    for word in DANGER_WORDS_REJECT:
        if word in text:
            return "reject"
    for word in DANGER_WORDS_REVIEW:
        if word in text:
            return "review"
    return "allow"


def extract_condition_from_text(site: str, text: str) -> str | None:
    """テキスト内からサイト固有のコンディションラベルを検出して返す。

    長いラベルを優先してマッチするため、キー長の降順で検索する。
    見つからない場合は None を返す。
    """
    key = _normalize_site(site)
    mapping = SITE_CONDITION_MAP.get(key, {})
    for label in sorted(mapping.keys(), key=len, reverse=True):
        if label in text:
            return label
    return None


def has_model_specificity(
    brand: str,
    model_tokens: set[str] | None = None,
    size_tokens: set[str] | None = None,
    line_tokens: set[str] | None = None,
    item_number: str | None = None,
    strict: bool | None = None,
) -> bool:
    """ブランドに対してモデル特定性が十分かチェックする。

    strict=None のとき STRICT_MODEL_CHECK_BRANDS に含まれるブランドは自動で strict=True になる。
    strict=False のときは常に True（チェックしない）を返す。
    """
    if strict is None:
        strict = brand.upper() in STRICT_MODEL_CHECK_BRANDS
    if not strict:
        return True

    specifics: dict[str, bool] = {
        "model_name": bool(model_tokens),
        "item_number": bool(item_number),
        "line_name":   bool(line_tokens),
        "size":        bool(size_tokens),
    }
    return any(specifics.get(field, False) for field in MODEL_SPECIFICITY_REQUIRED)


# 型番らしい文字列を検出するパターン
# 例: 1BH176, GG0025O, BR20AG, BN2849 など（英字+数字 or 数字+英字、4〜10文字）
_ITEM_NUMBER_RE = re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]{4,10}\b")


def _has_item_number(title: str) -> bool:
    """タイトル文字列に型番らしいトークンが含まれるか判定する。"""
    return bool(_ITEM_NUMBER_RE.search(title.upper()))


def check_model_specificity(brand: str, item: dict) -> tuple[str, str]:
    """analyzerの row dict を受け取り、モデル特定性を判定する。

    STRICT_MODEL_CHECK_BRANDS 以外のブランドは常に ("allow", "") を返す。

    item dict で参照するキー:
        model_signature (str)  : 非空ならモデル名特定済み
        model_match     (bool) : メルカリ sold とのモデル一致
        line_match      (bool) : ライン名一致
        source_has_size (bool) : サイズトークンあり
        source_title    (str)  : 型番正規表現マッチに使用

    Returns:
        ("allow",  reason) : 特定性あり
        ("review", reason) : 特定性不足
    """
    if brand.upper() not in STRICT_MODEL_CHECK_BRANDS:
        return "allow", ""

    specifics: dict[str, bool] = {
        "model_name": bool(item.get("model_signature")),
        "item_number": _has_item_number(item.get("source_title", "")),
        "line_name":   bool(item.get("line_match")),
        "size":        bool(item.get("source_has_size")),
    }

    met = [field for field in MODEL_SPECIFICITY_REQUIRED if specifics.get(field)]
    if met:
        return "allow", f"モデル特定済: {', '.join(met)}"

    return "review", f"モデル特定不足（{brand} はハイブランド厳格チェック対象）"


def evaluate_condition(
    site: str,
    raw_condition: str | None,
    description: str = "",
    brand: str = "",
    model_tokens: set[str] | None = None,
    size_tokens: set[str] | None = None,
    line_tokens: set[str] | None = None,
    item_number: str | None = None,
) -> tuple[str, str]:
    """総合コンディション評価。

    優先順:
      1. ランク reject → 即 reject
      2. 危険語 reject → 即 reject
      3. ランク review or 危険語 review → review
      4. ハイブランドのモデル特定不足 → review
      5. ランク不明（サイト未対応 or ラベル未定義）→ review
      6. allow

    Args:
        site:          scraper.site_name
        raw_condition: サイトから取得した生のコンディション文字列（Noneも可）
        description:   商品説明文（危険語チェックに使用）
        brand:         ブランド名（モデル特定性チェックに使用）
        model_tokens:  抽出済みモデルトークン
        size_tokens:   抽出済みサイズトークン
        line_tokens:   抽出済みライントークン
        item_number:   型番文字列

    Returns:
        (decision, reason):
            decision: "allow" | "review" | "reject"
            reason:   判断理由の説明文字列
    """
    # 1. ランク変換（直接マッチ → テキスト内ラベル探索の順）
    rank: str | None = None
    if raw_condition:
        rank = normalize_condition(site, raw_condition)
        if rank is None:
            found_label = extract_condition_from_text(site, raw_condition)
            if found_label:
                rank = normalize_condition(site, found_label)

    rank_decision = classify_by_rank(rank)

    if rank_decision == "reject":
        return "reject", f"ランク除外: {rank}"

    # 2. 危険語チェック
    word_decision = check_description_words(description)
    if word_decision == "reject":
        matched = next((w for w in DANGER_WORDS_REJECT if w in description), "")
        return "reject", f"危険語除外: 「{matched}」"

    # 3. review マージ
    if rank_decision == "review" or word_decision == "review":
        parts: list[str] = []
        if rank_decision == "review":
            parts.append(f"ランク保留: {rank}")
        if word_decision == "review":
            matched = next((w for w in DANGER_WORDS_REVIEW if w in description), "")
            parts.append(f"要確認語: 「{matched}」")
        return "review", " / ".join(parts)

    # 4. ハイブランドのモデル特定性チェック
    if brand.upper() in STRICT_MODEL_CHECK_BRANDS:
        if not has_model_specificity(brand, model_tokens, size_tokens, line_tokens, item_number):
            return "review", "モデル特定不足（ハイブランド要確認）"

    # 5. ランク不明 → 保留
    if rank_decision == "unknown":
        return "review", f"ランク不明: raw='{raw_condition}'"

    # 6. 通過
    return "allow", f"ランク: {rank}"
