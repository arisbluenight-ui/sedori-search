import asyncio, sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from config import ScraperConfig
from scrapers.mercari import MercariScraper
from vision_judge import vision_compare_sold_items

def pick_url(x):
    return (
        getattr(x, 'item_url', None)
        or getattr(x, 'url', None)
        or getattr(x, 'listing_url', None)
        or ''
    )

def pick_images(x):
    return (
        getattr(x, 'image_urls', None)
        or getattr(x, 'images', None)
        or []
    )

async def poc():
    print('=== Vision PoC 最小テスト ===')
    config = ScraperConfig(
        max_source_price=60000,
        max_items=3,
    )
    s = MercariScraper(config)

    items = s.search('IACUCCI', sold=True)
    print(f'[メルカリ] 取得件数: {len(items)}件')

    if len(items) < 2:
        print(f'SOLD商品が少なすぎます: {len(items)}件')
        return


    source = {
        'title': items[0].title,
        'price': items[0].price,
        'item_url': pick_url(items[0]),
        'image_urls': pick_images(items[0]),
    }

    sold = [{
        'item_url': pick_url(i),
        'title': i.title,
        'price': i.price,
        'image_urls': pick_images(i),
    } for i in items[1:]]

    print(f"source: {source['title'][:40]}")
    print(f'比較対象: {len(sold)}件')
    print('Vision API呼び出し中...')

    try:
        result = vision_compare_sold_items(source, sold, 'IACUCCI', 'ギブリ')
        print(f"confirmed: {result.get('sold_count_vision_confirmed')}")
        print(f"near:      {result.get('sold_count_near_variant')}")
        print(f"rejected:  {result.get('vision_reject_count')}")
        print(f"confidence:{result.get('model_match_confidence')}")
        print(f"summary:   {result.get('vision_reason_summary')}")
    except Exception as e:
        print(f'Visionテストで例外: {type(e).__name__}: {e}')

    print('=== 完了 ===')

asyncio.run(poc())