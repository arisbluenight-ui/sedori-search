from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"[¥￥][\d,]+")


class VectorParkScraper(PlaywrightScraper):
    site_name = "ベクトルパーク"
    base_url = "https://vector-park.jp/list/"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        # vector-park uses ?kw= for keyword search (server-side rendered, no JS needed)
        return f"{self.base_url}?kw={encode_query(brand)}"

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            # Server-side rendered: fetch_html_http works and respects URL params
            # Playwright loads JS that overrides search results with default listings
            html = self.fetch_html_http(self.build_search_url(brand))
            soup = BeautifulSoup(html, "html.parser")
            anchors = soup.select("a[href*='/item/']")[: self.config.max_items]
            listings: list[Listing] = []
            for anchor in anchors:
                href = str(anchor.get("href", ""))
                if not href:
                    continue
                url = f"https://vector-park.jp{href}" if href.startswith("/") else href
                # Title is stored in img alt attribute
                imgs = anchor.select("img[alt]")
                title = self.clean_title(imgs[0].get("alt", "")) if imgs else ""
                # Price is in the grandparent container element
                container = anchor.parent and anchor.parent.parent
                container_text = container.get_text(" ", strip=True) if container else ""
                price_match = _PRICE_RE.search(container_text)
                price_text = price_match.group(0) if price_match else container_text
                listing = self.make_listing(brand, title, price_text, url)
                if listing and listing.price <= self.config.effective_max_price(brand):
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(anchors))
            if not listings:
                logger.warning("[ベクトルパーク] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[ベクトルパーク] %s の取得に失敗しました: %s", brand, error)
            return []
