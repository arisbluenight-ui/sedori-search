from __future__ import annotations

import logging

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)


class BrandearScraper(PlaywrightScraper):
    site_name = "ブランディア"
    base_url = "https://auction.brandear.jp/search/list/"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        # Correct param is SearchFullText= (Keyword= redirects to homepage)
        return f"{self.base_url}?SearchFullText={encode_query(brand)}"

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_html(self.build_search_url(brand))
            # Card: div.item; title: img alt in div.img; price: span.price2; url: a in div.item_name
            cards = self.parse_cards(html, ["div.item"])[: self.config.max_items]
            listings: list[Listing] = []
            for card in cards:
                # Title from img alt (includes both English and Japanese brand names)
                title = self.pick_attr(card, ["div.img img[alt]", "img[alt]"], "alt")
                if not title:
                    title = self.pick_attr(card, ["div.item_name a[title]", "a[title]"], "title")
                # Price in span.price2 (numeric string like "5,009")
                price_text = self.pick_text(card, ["span.price2", "[class*='price']"])
                url = self.pick_attr(card, ["a[href*='/search/detail/']", "a[href]"], "href")
                if url.startswith("/"):
                    url = f"https://auction.brandear.jp{url}"
                listing = self.make_listing(brand, title, price_text, url)
                if listing and listing.price <= self.config.max_source_price:
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards))
            if not listings:
                logger.warning("[ブランディア] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[ブランディア] %s の取得に失敗しました: %s", brand, error)
            return []
