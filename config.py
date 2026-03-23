from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


PRIORITY_BRANDS = [
    # B層（日本発・根強いファン）
    "ペッレモルビダ",
    "MOTHERHOUSE",
    "genten",
    "Dakota",
    "LAST CROPS",
    "A VACATION",
    "YOUNG&OLSEN",
    # C層（セレクト感・上振れ期待）
    "POLENE",
    "WANDLER",
    "VASIC",
    "Aeta",
    "MAISON CANAU",
    "ZANCHETTI AMLETO",
    "J&M Davidson",
    "JIL SANDER",
    "MARNI",
    "TOD'S",
    "ANTEPRIMA",
    "Sacai",
    "PATOU",
    "PACO RABANNE",
    "STATE OF ESCAPE",
    # 追加ブランド
    "SOMES",
    "Mystery Ranch",
    "TOM FORD",
    "IACUCCI",
    "3.1 Phillip Lim",
    "Pierre Hardy",
    "万双",
    "Glenroyal",
    "HERZ",
    # A層（即売れ）
    "PRADA",
    "GUCCI",
    "LOEWE",
    # A層（残留分）
    "Longchamp",
    "Mulberry",
    "Anya Hindmarch",
    "BURBERRY",
    "MONCLER",
    "JIMMY CHOO",
    "TUMI",
]


BRAND_ALIASES: dict[str, list[str]] = {
    "Longchamp": ["ロンシャン"],
    "Kate Spade": ["ケイトスペード"],
    "FURLA": ["フルラ"],
    "IL BISONTE": ["イルビゾンテ"],
    "TUMI": ["トゥミ"],
    "LeSportsac": ["レスポートサック"],
    "MONCLER": ["モンクレール"],
    "JIMMY CHOO": ["ジミーチュウ"],
    "IACUCCI": ["イアクッチ"],
    "LAST CROPS": ["ラストクロップス", "LASTCROPS"],
    "A VACATION": ["アヴァケーション"],
    "MARNI": ["マルニ"],
    "BURBERRY": ["バーバリー"],
    "COACH": ["コーチ"],
    "ANTEPRIMA": ["アンテプリマ"],
    "JIL SANDER": ["ジルサンダー"],
    "Acne Studios": ["アクネ"],
    "POLENE": ["ポレーヌ"],
    "SUPREME": ["シュプリーム"],
    "PATOU": ["パトゥ"],
    "PACO RABANNE": ["パコラバンヌ"],
    "MOTHERHOUSE": ["マザーハウス"],
    "Sacai": ["サカイ"],
    "Porter": ["ポーター"],
    "PORTER": ["ポーター"],
    "PORTER CLASSIC": ["ポータークラシック"],
    "Dakota": ["ダコタ"],
    "genten": ["ゲンテン"],
    "A.P.C.": ["アーペーセー"],
    "HUNTING WORLD": ["ハンティングワールド"],
    "HENDER SCHEME": ["ヘンダースキーム"],
    "TOPKAPI": ["トプカピ"],
    "CLEDRAN": ["クレドラン"],
    "MARGARET HOWELL": ["マーガレットハウエル"],
    "Mystery Ranch": ["ミステリーランチ"],
    "TOM FORD": ["トムフォード"],
    "Glenroyal": ["グレンロイヤル"],
    "HERZ": ["ヘルツ"],
    "Pierre Hardy": ["ピエールアルディ"],
    "3.1 Phillip Lim": ["スリーワンフィリップリム"],
    "SOEUR": ["スール"],
    "SOMES": ["ソメスサドル", "ソメス"],
    "万双": ["万双"],
    "土屋鞄": ["土屋鞄製作所"],
    "PRADA": ["プラダ"],
    "GUCCI": ["グッチ"],
    "LOEWE": ["ロエベ"],
}


BRAND_MAX_PRICE: dict[str, int] = {
    # 通常上限: ¥70,000（ここまでは通常フロー）
    "PRADA":    70_000,
    "GUCCI":    70_000,
    "LOEWE":    70_000,
    "BURBERRY": 70_000,
    "CELINE":   70_000,
    "FENDI":    70_000,
    "GIVENCHY": 70_000,
    "MIU MIU":  70_000,
}

# ¥BRAND_MAX_PRICE超〜ここまでは review_required=True で保留出力
BRAND_MAX_PRICE_REVIEW: dict[str, int] = {
    "PRADA":    80_000,
    "GUCCI":    80_000,
    "LOEWE":    80_000,
    "BURBERRY": 80_000,
    "CELINE":   80_000,
    "FENDI":    80_000,
    "GIVENCHY": 80_000,
    "MIU MIU":  80_000,
}


BRAND_SELL_SPEED: dict[str, str] = {
    "MOTHERHOUSE": "fast",
    "LAST CROPS": "fast",
    "IACUCCI": "fast",
    "ペッレモルビダ": "medium",
    "YOUNG&OLSEN": "medium",
    "Anya Hindmarch": "medium",
    "VASIC": "slow",
    "WANDLER": "slow",
    "J&M Davidson": "slow",
    "PRADA": "fast",
    "GUCCI": "fast",
    "LOEWE": "fast",
}


SOURCE_SITES = [
    "楽天市場",
    "Yahooショッピング",
    "RAGTAG",
    "ALLU",
    "BRAND OFF",
    "RECLO",
    "KOMEHYO",
    "ベクトルパーク",
    "トレファクファッション",
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
    "付属品のみ",
    "バッグインバッグ",
    "本体以外",
    "ジャンク",
    "難あり",
    "ダストバッグ",
    "dust bag",
    "保存袋",
    # 靴・シューズ類
    "靴",
    "シューズ",
    "サンダル",
    "ミュール",
    "スニーカー",
    "ブーツ",
    "パンプス",
    "ヒール",
    "shoes",
    "sneakers",
    "boots",
    "sandals",
    "pumps",
    "loafers",
    "mules",
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
    "black": ["black", "blk", "bk", "noir", "nero", "ブラック", "黒"],
    "white": ["white", "wht", "wh", "ivory", "off white", "offwhite", "ホワイト", "白", "アイボリー", "オフホワイト", "生成り"],
    "beige": ["beige", "greige", "taupe", "ベージュ", "グレージュ", "エトープ"],
    "brown": ["brown", "brw", "bro", "brn", "camel", "cognac", "ブラウン", "茶", "キャメル", "コニャック"],
    "blue": ["navy", "nvy", "nv", "indigo", "blue", "ネイビー", "ブルー", "青", "インディゴ"],
    "green": ["green", "khaki", "olive", "グリーン", "緑", "カーキ", "オリーブ"],
    "red": ["red", "rd", "bordeaux", "wine", "レッド", "赤", "ボルドー", "ワイン"],
    "pink": ["pink", "ピンク"],
    "purple": ["purple", "パープル", "紫", "ラベンダー", "lavender"],
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


STRICT_MODEL_BRANDS = {"POLENE", "IACUCCI", "MARNI"}


# モデル名なし除外ルールの対象外ブランド
# POLENE は strict_signature で別管理のため除外不要
# モデル名を使わないブランドが出た場合はここに追加する
NO_MODEL_REQUIRED_BRANDS: set[str] = {"POLENE", "IACUCCI", "MARNI", "A VACATION"}


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


IACUCCI_MODEL_PATTERNS = {
    "ghibli": ["ギブリ", "ghibli", "GHIBLI"],
    "sorbetto": ["ソルベット", "sorbetto", "SORBETTO"],
    "velar": ["ベラール", "VELAR", "velar", "ヴェラール"],
}


MARNI_MODEL_PATTERNS = {
    "museo": ["ミュゼオ", "museo", "MUSEO"],
    "trunk": ["トランク", "trunk", "TRUNK", "トランクバッグ"],
}


# STRICT_MODEL_BRANDS のメルカリ追加検索クエリ
# ブランド名 + モデル代表名 で sold データを補強する
STRICT_MODEL_SEARCH_QUERIES: dict[str, list[str]] = {
    "POLENE": ["POLENE numero"],
    "IACUCCI": ["IACUCCI ギブリ", "IACUCCI ソルベット", "IACUCCI ghibli", "IACUCCI sorbetto", "イアクッチ ギブリ", "イアクッチ ソルベット"],
    "MARNI": ["MARNI ミュゼオ", "MARNI トランク"],
    "LAST CROPS": ["LAST CROPS バッグ", "ラストクロップス バッグ"],
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
    min_mercari_sample_count: int = 3
    user_specified_brands: bool = False
    full_source_scan: bool = False
    active_source_sites: list[str] = field(default_factory=lambda: PRIMARY_SOURCE_SITES.copy())
    deep_dive_brands: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=lambda: PRIORITY_BRANDS.copy())

    def effective_max_price(self, brand: str) -> int:
        """ブランド別仕入れ上限（保留ライン）を返す。未登録ブランドは通常上限。"""
        return BRAND_MAX_PRICE_REVIEW.get(brand, self.max_source_price)
