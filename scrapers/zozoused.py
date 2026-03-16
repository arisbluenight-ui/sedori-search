from __future__ import annotations

import logging

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)


class ZozousedScraper(PlaywrightScraper):
    site_name = "ZOZOUSED"
    base_url = "https://zozo.jp/search"
    result_selectors = [
        "li.search-result-item",
        "li[class*='searchResultItem']",
        "a[href*='/used/']",
        "[data-testid='search-result-item']",
    ]

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        return f"{self.base_url}?used=1&p_keyv={encode_query(brand)}"

    def fetch_search_html(self, brand: str) -> str:
        encoded_brand = encode_query(brand)
        search_url = self.build_search_url(brand)
        logger.info("[ZOZOUSED] brand_query=%s encoded_query=%s url=%s", brand, encoded_brand, search_url)
        return self.fetch_html_with_options(
            search_url,
            goto_timeout_ms=30000,
            wait_until="load",
            wait_for_selectors=self.result_selectors,
            selector_timeout_ms=5000,
            retries=1,
        )

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_search_html(brand)
            cards = self.parse_cards(
                html,
                self.result_selectors,
            )[: self.config.max_items]
            listings: list[Listing] = []
            for card in cards:
                title = self.pick_text(
                    card,
                    ["[class*='searchResultItemName']", "[class*='SearchResultItem_name']", "h3", "a"],
                )
                price_text = self.pick_text(
                    card,
                    ["[class*='searchResultItemPrice']", "[class*='SearchResultItem_price']", "[class*='price']", "span"],
                )
                item_url = self.pick_attr(card, ["a[href*='/used/']", "a[href]"], "href")
                if item_url.startswith("/"):
                    item_url = f"https://zozo.jp{item_url}"
                listing = self.make_listing(brand, title, price_text, item_url)
                if listing and listing.price <= self.config.max_source_price:
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards))
            if not listings:
                logger.warning("[ZOZOUSED] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[ZOZOUSED] %s の取得に失敗しました: %s", brand, error)
            return []
