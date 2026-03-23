from __future__ import annotations

import logging

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)


class KomehyoScraper(PlaywrightScraper):
    site_name = "KOMEHYO"
    base_url = "https://komehyo.jp/search"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        return f"{self.base_url}/?q={encode_query(brand)}"

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_html_http(self.build_search_url(brand))
            cards = self.parse_cards(html, ["li.p-lists__item"])[: self.config.max_items]
            listings: list[Listing] = []
            for card in cards:
                brand_label = self.pick_text(card, [".p-link__txt--brand"])
                if brand_label and not self.brand_matches(brand, brand_label):
                    continue

                title = self.pick_text(card, [".p-link__txt--productsname"])
                if brand_label and not self.brand_matches(brand, title):
                    title = f"{brand_label} {title}".strip()
                price_text = self.pick_text(card, [".p-link__txt--price-sale", ".p-link__txt--price"])
                item_url = self.pick_attr(card, ["a.p-link.p-link--card[href]", "a[href*='/product/']", "a[href]"], "href")
                if item_url.startswith("/"):
                    item_url = f"https://komehyo.jp{item_url}"

                listing = self.make_listing(brand, title, price_text, item_url)
                if listing and listing.price <= self.config.effective_max_price(brand):
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards))
            if not listings:
                logger.warning("[KOMEHYO] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[KOMEHYO] %s の取得に失敗しました: %s", brand, error)
            return []
