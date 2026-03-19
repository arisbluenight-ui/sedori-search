from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)

# Product detail URLs follow /store/{16-digit-id}/c{7-digit-code}/
_PRODUCT_URL_RE = re.compile(r"/store/\d+/c\d+")
# ¥-prefixed price pattern
_PRICE_RE = re.compile(r"[¥￥][\d,]+")


class TrefacFashionScraper(PlaywrightScraper):
    site_name = "トレファクファッション"
    base_url = "https://www.trefac.jp/store/tcpsb"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        return f"{self.base_url}/?srchword={encode_query(brand)}&step=1&order=new"

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_html(self.build_search_url(brand))
            soup = BeautifulSoup(html, "html.parser")
            # Product links follow /store/{id}/c{code}/ pattern
            anchors = [a for a in soup.find_all("a", href=_PRODUCT_URL_RE)][: self.config.max_items]
            listings: list[Listing] = []
            for anchor in anchors:
                href = str(anchor.get("href", ""))
                url = f"https://www.trefac.jp{href}" if href.startswith("/") else href
                title = self.clean_title(anchor.get_text(" ", strip=True))
                # Price is typically a text node in the parent <li>, outside the <a>
                parent = anchor.parent
                parent_text = parent.get_text(" ", strip=True) if parent else ""
                price_match = _PRICE_RE.search(parent_text)
                price_text = price_match.group(0) if price_match else parent_text
                listing = self.make_listing(brand, title, price_text, url)
                if listing and listing.price <= self.config.max_source_price:
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(anchors))
            if not listings:
                logger.warning("[トレファクファッション] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[トレファクファッション] %s の取得に失敗しました: %s", brand, error)
            return []
