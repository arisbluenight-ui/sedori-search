from __future__ import annotations

import logging

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import detect_availability_status, encode_query


logger = logging.getLogger(__name__)


class YahooShoppingScraper(PlaywrightScraper):
    site_name = "Yahooショッピング"
    base_url = "https://shopping.yahoo.co.jp/search"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        return f"{self.base_url}?p={encode_query(brand)}&X=4&pf=0&pt={self.config.effective_max_price(brand)}"

    def _card_selectors(self) -> list[str]:
        return ["div.SearchResult_SearchResultItem__mJ7vY", "div[class*='SearchResult_SearchResultItem__']"]

    def _title_selectors(self) -> list[str]:
        return [
            "a.SearchResult_SearchResultItem__detailLink__G4Top span.ItemTitle_SearchResultItemTitle__fy4bB",
            "a[class*='SearchResult_SearchResultItem__detailLink__'] span[class*='ItemTitle_SearchResultItemTitle__']",
            "a[class*='SearchResult_SearchResultItem__detailLink__']",
        ]

    def _price_selectors(self) -> list[str]:
        return ["span.ItemPrice_ItemPrice__2t7fx", "span[class*='ItemPrice_ItemPrice__']"]

    def _link_selectors(self) -> list[str]:
        return ["a.SearchResult_SearchResultItem__detailLink__G4Top", "a[class*='SearchResult_SearchResultItem__detailLink__']"]

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_html_http(self.build_search_url(brand))
            cards = self.parse_cards(html, self._card_selectors())[: self.config.max_items]
            listings: list[Listing] = []
            for card in cards:
                brand_label = self.pick_text(
                    card,
                    [
                        "p.ItemBrand_SearchResultItemBrand__kAW_y a",
                        "p[class*='ItemBrand_SearchResultItemBrand__'] a",
                    ],
                )
                if brand_label and not self.brand_matches(brand, brand_label):
                    continue

                title = self.pick_text(card, self._title_selectors())
                if brand_label and not self.brand_matches(brand, title):
                    title = f"{brand_label} {title}".strip()
                price_text = self.pick_text(card, self._price_selectors())
                item_url = self.pick_attr(card, self._link_selectors(), "href")
                availability_status = detect_availability_status(card.get_text(" ", strip=True))
                listing = self.make_listing(
                    brand,
                    title,
                    price_text,
                    item_url,
                    sold=False,
                    metadata={"availability_status": availability_status},
                )
                if listing and listing.price <= self.config.effective_max_price(brand):
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards))
            if not listings:
                logger.warning("[Yahooショッピング] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[Yahooショッピング] %s の取得に失敗しました: %s", brand, error)
            return []
