from __future__ import annotations

import logging

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import encode_query


logger = logging.getLogger(__name__)


class MercariScraper(PlaywrightScraper):
    site_name = "メルカリ"
    base_url = "https://jp.mercari.com/search"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str, sold: bool) -> str:
        params = [
            f"keyword={encode_query(brand)}",
            "status=on_sale" if not sold else "status=sold_out",
            f"price_max={self.config.max_source_price}" if not sold else "",
        ]
        query = "&".join(part for part in params if part)
        return f"{self.base_url}?{query}"

    def _card_selectors(self) -> list[str]:
        return [
            "li[data-testid='item-cell']",
            "div[data-testid='item-cell']",
            "mer-item-thumbnail",
            "section li",
        ]

    def _title_selectors(self) -> list[str]:
        return [
            "[data-testid='thumbnail-item-name']",
            "mer-text",
            "h3",
            "p",
        ]

    def _price_selectors(self) -> list[str]:
        return [
            "[data-testid='thumbnail-item-price']",
            "[aria-label*='価格']",
            "span",
        ]

    def _link_selectors(self) -> list[str]:
        return [
            "a[href*='/item/']",
            "a",
        ]

    def search(self, brand: str, sold: bool = False) -> list[Listing]:
        url = self.build_search_url(brand, sold=sold)
        try:
            html = self.fetch_html(url)
            cards = self.parse_cards(html, self._card_selectors())[: self.config.max_items]
            listings: list[Listing] = []
            for card in cards:
                title = self.pick_text(card, self._title_selectors())
                price_text = self.pick_text(card, self._price_selectors())
                relative_url = self.pick_attr(card, self._link_selectors(), "href")
                if relative_url and relative_url.startswith("/"):
                    relative_url = f"https://jp.mercari.com{relative_url}"
                listing = self.make_listing(brand, title, price_text, relative_url, sold=sold)
                if listing:
                    listings.append(listing)
            if not listings:
                logger.warning("[メルカリ] %s の%s取得件数は0件です", brand, "売り切れ" if sold else "販売中")
            return listings
        except Exception as error:
            logger.warning("[メルカリ] %s の取得に失敗しました: %s", brand, error)
            return []
