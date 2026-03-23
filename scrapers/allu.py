from __future__ import annotations

import logging

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)


class AlluScraper(PlaywrightScraper):
    site_name = "ALLU"
    base_url = "https://ec-jp.allu-official.com/search"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        return f"{self.base_url}?q={encode_query(brand)}"

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_html(self.build_search_url(brand))
            cards = self.parse_cards(html, ["div.p-productsSimilar__item"])[: self.config.max_items]
            listings: list[Listing] = []
            for card in cards:
                title = self.pick_text(card, ["p.p-productsSimilar__info__ttl", "p[class*='ttl']", "p[class*='name']"])
                price_text = self.pick_text(card, ["p.p-productsSimilar__info__price", "p[class*='price']"])
                url = self.pick_attr(card, ["a[href*='/market/items/']", "a[href]"], "href")
                if url.startswith("/"):
                    url = f"https://ec-jp.allu-official.com{url}"
                listing = self.make_listing(brand, title, price_text, url)
                if listing and listing.price <= self.config.effective_max_price(brand):
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards))
            if not listings:
                logger.warning("[ALLU] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[ALLU] %s の取得に失敗しました: %s", brand, error)
            return []
