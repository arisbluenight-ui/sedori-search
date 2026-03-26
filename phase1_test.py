import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def test(label, items):
    print(f"\n{'='*40}\n[{label}]\n{'='*40}")
    if not items:
        print("  0件"); return
    filled = sum(1 for i in items if getattr(i, "image_urls", []))
    print(f"  取得: {len(items)}件 / image_urlsあり: {filled}件 / 空: {len(items)-filled}件")
    first = items[0]
    print(f"  title: {first.title}")
    urls = getattr(first, "image_urls", "【フィールドなし】")
    print(f"  image_urls: {urls}")
    if isinstance(urls, list) and urls:
        print(f"  URL例: {urls[0][:80]}")
    elif isinstance(urls, list):
        print("  空リスト（セレクター要確認）")
    else:
        print("  フィールドなし（analyzer.pyパッチ要確認）")

from scrapers.mercari import MercariScraper
from scrapers.ragtag import RagtagScraper
from config import ScraperConfig

cfg = ScraperConfig()
m = MercariScraper(cfg)
r = RagtagScraper(cfg)

print("Mercari SOLD テスト中...")
items_m = m.search("LOEWE", sold=True)
test("Mercari SOLD", items_m[:5])

print("\nRAGTAG テスト中...")
items_r = r.search("LOEWE")
test("RAGTAG", items_r[:5])

print("\nテスト完了")
