import re, shutil, sys
from pathlib import Path

BASE = Path(".")
ANALYZER = BASE / "analyzer.py"
MERCARI  = BASE / "scrapers" / "mercari.py"
RAGTAG   = BASE / "scrapers" / "ragtag.py"

def backup(p): shutil.copy(p, p.with_suffix(p.suffix + ".bak")); print(f"  バックアップ: {p.name}.bak")
def read(p): return p.read_text(encoding="utf-8")
def write(p, t): p.write_text(t, encoding="utf-8")

# Patch 1: analyzer.py
print("\n=== Patch 1: analyzer.py ===")
src = read(ANALYZER)
if "image_urls" in src:
    print("  スキップ（既存）")
else:
    backup(ANALYZER)
    for pat in [r"(    sold_count\s*:.*\n)", r"(    score\s*:.*\n)", r"(    review_required\s*:.*\n)", r"(    skip_reason\s*:.*\n)"]:
        if re.search(pat, src):
            write(ANALYZER, re.sub(pat, r"\1    image_urls: list[str] = field(default_factory=list)\n", src, count=1))
            print("  image_urls 追加完了"); break
    else:
        print("  手動追加必要: Listingクラスのフィールド末尾に以下を追加\n  image_urls: list[str] = field(default_factory=list)")

# Patch 2: mercari.py
print("\n=== Patch 2: mercari.py ===")
src = read(MERCARI)
if "image_urls" in src:
    print("  スキップ（既存）")
else:
    backup(MERCARI)
    src = re.sub(
        r"([ \t]+)(listing\s*=\s*self\.make_listing\()",
        lambda m: m.group(1)+'imgs = card.select("img")[:3]\n'+m.group(1)+'image_urls = [u for img in imgs for u in [img.get("src") or img.get("data-src") or ""] if u.startswith("http")]\n'+m.group(1)+m.group(2),
        src, count=1)
    src = re.sub(
        r"([ \t]+)(listings\.append\(listing\))",
        lambda m: m.group(1)+"listing.image_urls = image_urls\n"+m.group(1)+m.group(2),
        src, count=1)
    write(MERCARI, src)
    print("  完了")

# Patch 3: ragtag.py
print("\n=== Patch 3: ragtag.py ===")
src = read(RAGTAG)
if "image_urls" in src:
    print("  スキップ（既存）")
else:
    backup(RAGTAG)
    src = re.sub(
        r"([ \t]+)(listing\s*=\s*self\.make_listing\()",
        lambda m: m.group(1)+'imgs = card.select("img.search-result__item-photo-img, img[src]")[:3]\n'+m.group(1)+'image_urls = [img["src"] for img in imgs if img.get("src","").startswith("http")]\n'+m.group(1)+m.group(2),
        src, count=1)
    src = re.sub(
        r"([ \t]+)(listings\.append\(listing\))",
        lambda m: m.group(1)+"listing.image_urls = image_urls\n"+m.group(1)+m.group(2),
        src, count=1)
    write(RAGTAG, src)
    print("  完了")

print("\nパッチ完了。次は: python phase1_test.py")
