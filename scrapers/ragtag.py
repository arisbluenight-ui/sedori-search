from __future__ import annotations

import logging

from bs4 import Tag

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import detect_availability_status, encode_query, normalize_text


logger = logging.getLogger(__name__)


class RagtagScraper(PlaywrightScraper):
    site_name = "RAGTAG"
    base_url = "https://www.ragtag.jp/search"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        return f"{self.base_url}?fr={encode_query(brand)}"

    def _extract_title(self, card: Tag) -> str:
        return self.pick_attr(card, ["img.search-result__item-photo-img", "img[alt]"], "alt")

    def fetch_availability_status(self, item_url: str) -> str:
        if not item_url:
            return "available"
        try:
            html = self.fetch_html_http(item_url)
        except Exception as error:
            logger.warning("[RAGTAG] 在庫状態の確認に失敗しました: %s", error)
            return "unknown"

        normalized_html = normalize_text(html)
        if "sold out" in normalized_html:
            return "SOLD OUT"
        if "取寄keep" in html or "お取り寄せ中" in html or "取り寄せ中" in html:
            return "お取り寄せ中"
        return detect_availability_status(html)

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        try:
            html = self.fetch_html_http(self.build_search_url(brand))
            cards = self.parse_cards(html, ["div.search-result__item"])[: self.config.max_items]
            listings: list[Listing] = []
            detail_page_count = 0
            for card in cards:
                brand_label = self.pick_text(card, [".search-result__name-brand"])
                if brand_label and not self.brand_matches(brand, brand_label):
                    continue

                title = self._extract_title(card)
                price_text = self.pick_text(card, [".search-result__price-proper"])
                item_url = self.pick_attr(card, ["a.search-result__item-link[href]", "a[href*='/item/']", "a[href]"], "href")
                if item_url.startswith("/"):
                    item_url = f"https://www.ragtag.jp{item_url}"

                availability_status = self.fetch_availability_status(item_url)
                detail_page_count += 1
                listing = self.make_listing(
                    brand,
                    title,
                    price_text,
                    item_url,
                    metadata={"availability_status": availability_status},
                )
                if listing and listing.price <= self.config.max_source_price:
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards), detail_page_count=detail_page_count)
            if not listings:
                logger.warning("[RAGTAG] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[RAGTAG] %s の取得に失敗しました: %s", brand, error)
            return []
