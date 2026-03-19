from __future__ import annotations

import logging
import re

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"[¥￥][\d,]+")
# Split before condition info (e.g. "商品の状態 : 中古B ¥25,190")
_CONDITION_RE = re.compile(r"\s*商品の状態\s*[:：].*$")


class SecondStreetScraper(PlaywrightScraper):
    site_name = "2nd STREET"
    base_url = "https://www.2ndstreet.jp/search"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        return f"{self.base_url}?keyword={encode_query(brand)}"

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_html(self.build_search_url(brand))
            # Card: li.itemCard (anchor inside contains title + condition + price as text)
            cards = self.parse_cards(html, [
                "li.itemCard",
                "li[class*='itemCard']",
                "li.itemListItem",
            ])[: self.config.max_items]
            listings: list[Listing] = []
            for card in cards:
                anchor = card.select_one("a[href*='/goods/detail/']") or card.select_one("a[href]")
                if not anchor:
                    continue
                href = str(anchor.get("href", ""))
                url = f"https://www.2ndstreet.jp{href}" if href.startswith("/") else href
                full_text = anchor.get_text(" ", strip=True)
                # Extract ¥-prefixed price explicitly (avoids picking up model numbers)
                price_match = _PRICE_RE.search(full_text)
                price_text = price_match.group(0) if price_match else ""
                # Strip condition+price suffix to get clean title
                title = self.clean_title(_CONDITION_RE.sub("", full_text))
                listing = self.make_listing(brand, title, price_text, url)
                if listing and listing.price <= self.config.max_source_price:
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards))
            if not listings:
                logger.warning("[2nd STREET] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[2nd STREET] %s の取得に失敗しました: %s", brand, error)
            return []
