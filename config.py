from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


PRIORITY_BRANDS = [
    "A VACATION",
    "SUPREME",
    "LAST CROPS",
    "Sacai",
    "TOD'S",
    "ZANCHETTI AMLETO",
    "soe",
    "PATOU",
    "BURBERRY",
    "MOTHERHOUSE",
    "ペッレモルビダ",
    "COACH",
    "JIL SANDER",
    "Acne Studios",
    "Porter",
    "Aeta",
    "MAISON CANAU",
    "CANDLER",
    "Morphee",
    "PACO RABANNE",
    "STATE OF ESCAPE",
    "PORTER",
    "PORTER CLASSIC",
    "YOUNG&OLSEN",
    "MARNI",
    "JIMMY CHOO",
    "MONCLER",
    "ANTEPRIMA",
    "POLENE",
    "イッセイミヤケ",
    "土屋鞄",
    "FURLA",
    "Kate Spade",
    "IL BISONTE",
    "Longchamp",
    "TUMI",
    "LeSportsac",
    "genten",
    "Dakota",
]


SOURCE_SITES = [
    "楽天市場",
    "Yahooショッピング",
    "RAGTAG",
    "ZOZOUSED",
    "ALLU",
    "BRAND OFF",
    "RECLO",
    "KOMEHYO",
    "2nd STREET",
    "ベクトルパーク",
    "トレファクファッション",
    "ブランディア",
    "Rehello by BOOKOFF",
]


PRIMARY_SOURCE_SITES = [
    "楽天市場",
    "Yahooショッピング",
    "RAGTAG",
]


UNAVAILABLE_STATUSES = {
    "SOLD OUT",
    "在庫なし",
    "お取り寄せ中",
    "入荷待ち",
    "売り切れ",
}


EXCLUDED_CANDIDATE_TERMS = {
    "風",
    "ノベルティ",
    "内ポケット",
    "インナーポーチ",
    "付属品",
    "バッグインバッグ",
    "本体以外",
    "ジャンク",
    "難あり",
}


NON_MAIN_PRODUCT_TERMS = {
    "内ポケット",
    "インナーポーチ",
    "付属品",
    "バッグインバッグ",
    "本体以外",
    "ストラップのみ",
    "チャーム",
    "キーホルダー",
    "ハンドルカバー",
}


MATERIAL_KEYWORDS = [
    "レザー",
    "本革",
    "革",
    "牛革",
    "ラムレザー",
    "カーフ",
    "ナイロン",
    "キャンバス",
    "エナメル",
    "スエード",
    "スウェード",
    "デニム",
    "コットン",
    "ポリエステル",
    "pvc",
    "leather",
    "nylon",
    "canvas",
    "suede",
    "cotton",
    "polyester",
]


SIZE_KEYWORDS = [
    "mini",
    "small",
    "medium",
    "large",
    "big",
    "ミニ",
    "スモール",
    "ミディアム",
    "ラージ",
    "ビッグ",
    "pm",
    "mm",
    "gm",
]


TARGET_CATEGORIES = ["バッグ", "リュック", "財布", "カードケース", "小物"]

TARGET_CATEGORY_KEYWORDS = {
    "バッグ": [
        "bag",
        "バッグ",
        "バック",
        "tote",
        "トート",
        "shoulder",
        "ショルダー",
        "handbag",
        "ハンドバッグ",
        "totebag",
        "ボストン",
        "クラッチ",
        "ポシェット",
    ],
    "リュック": [
        "rucksack",
        "backpack",
        "バックパック",
        "リュック",
    ],
    "財布": [
        "wallet",
        "財布",
        "ウォレット",
        "coin case",
        "コインケース",
        "二つ折り",
        "三つ折り",
        "長財布",
    ],
    "カードケース": [
        "card case",
        "カードケース",
        "名刺入れ",
        "pass case",
        "パスケース",
    ],
    "小物": [
        "pouch",
        "ポーチ",
        "accessory",
        "アクセサリー",
        "key case",
        "キーケース",
    ],
}


BAG_KEYWORDS = sorted({keyword for keywords in TARGET_CATEGORY_KEYWORDS.values() for keyword in keywords})


DISCOVERY_EXCLUDED_TERMS = {
    "black",
    "white",
    "beige",
    "brown",
    "blue",
    "green",
    "red",
    "pink",
    "metallic",
    "ブラック",
    "ホワイト",
    "ベージュ",
    "ブラウン",
    "ネイビー",
    "ブルー",
    "グリーン",
    "レッド",
    "ピンク",
    "シルバー",
    "ゴールド",
    "黒",
    "白",
    "茶",
    "青",
    "緑",
    "赤",
    "金",
    "銀",
    "バッグ",
    "バック",
    "ショルダー",
    "トート",
    "ハンドバッグ",
    "リュック",
    "バックパック",
    "財布",
    "ウォレット",
    "カードケース",
    "コインケース",
    "名刺入れ",
    "ケース",
    "ポーチ",
    "レザー",
    "ナイロン",
    "キャンバス",
    "スエード",
    "本革",
    "革",
    "new",
    "used",
    "中古",
    "新品",
    "レディース",
    "メンズ",
    "ユニセックス",
    "小物",
}


AMBIGUOUS_BRANDS = {
    "no brand",
    "nobrand",
    "non brand",
    "unknown",
    "other",
    "brand",
    "ノーブランド",
    "その他",
    "不明",
}


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


COLOR_RULES = {
    "black": ["black", "blk", "noir", "nero", "ブラック", "黒"],
    "white": ["white", "ivory", "off white", "offwhite", "ホワイト", "白", "アイボリー", "オフホワイト", "生成り"],
    "beige": ["beige", "greige", "taupe", "ベージュ", "グレージュ", "エトープ"],
    "brown": ["brown", "camel", "cognac", "ブラウン", "茶", "キャメル", "コニャック"],
    "blue": ["navy", "indigo", "blue", "ネイビー", "ブルー", "青", "インディゴ"],
    "green": ["green", "khaki", "olive", "グリーン", "緑", "カーキ", "オリーブ"],
    "red": ["red", "bordeaux", "wine", "レッド", "赤", "ボルドー", "ワイン"],
    "pink": ["pink", "ピンク"],
    "yellow": ["yellow", "イエロー", "黄", "マスタード"],
    "metallic": ["silver", "gold", "シルバー", "ゴールド", "銀", "金"],
}


RAW_COLOR_VARIANTS = sorted(
    {
        variant
        for variants in COLOR_RULES.values()
        for variant in variants
    },
    key=len,
    reverse=True,
)


STRICT_MODEL_BRANDS = {"POLENE"}


POLENE_MODEL_PATTERNS = {
    "numero-un": ["numero un", "numero1", "numéro un", "numero one", "numero un nano", "numero un mini"],
    "numero-sept": ["numero sept", "numéro sept", "numero 7", "sept"],
    "numero-neuf": ["numero neuf", "numéro neuf", "numero 9", "neuf", "nine"],
    "numero-dix": ["numero dix", "numéro dix", "numero 10", "dix"],
    "numero-huit": ["numero huit", "numéro huit", "numero 8", "huit"],
    "cyme": ["cyme"],
    "beri": ["beri"],
    "umi": ["umi"],
    "tonca": ["tonca"],
    "nodde": ["nodde"],
    "mokki": ["mokki"],
    "toni": ["toni"],
}


@dataclass(slots=True)
class ScraperConfig:
    timeout_ms: int = 15000
    headless: bool = True
    min_profit_rate: float = 0.30
    max_source_price: int = 60000
    max_items: int = 50
    batch_size: int = 8
    enable_auto_brand_discovery: bool = True
    auto_brand_limit: int = 10
    request_delay_seconds: float = 0.8
    navigation_wait_until: str = "domcontentloaded"
    mercari_fee_rate: float = 0.10
    min_profit_amount: int = 3000
    final_output_min_profit: int = 10000
    min_mercari_sample_count: int = 5
    user_specified_brands: bool = False
    full_source_scan: bool = False
    active_source_sites: list[str] = field(default_factory=lambda: PRIMARY_SOURCE_SITES.copy())
    deep_dive_brands: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=lambda: PRIORITY_BRANDS.copy())
