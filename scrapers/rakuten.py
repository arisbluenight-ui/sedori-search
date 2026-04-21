from __future__ import annotations

import json
import logging
import re

from analyzer import Listing
from config import ScraperConfig
from scrapers.base import PlaywrightScraper
from utils import detect_availability_status, encode_query


logger = logging.getLogger(__name__)


class RakutenScraper(PlaywrightScraper):
    site_name = "楽天市場"
    base_url = "https://search.rakuten.co.jp/search/mall"

    def __init__(self, config: ScraperConfig) -> None:
        super().__init__(config)

    def build_search_url(self, brand: str) -> str:
        # 楽天はパス形式のURL。アポストロフィ(%27)はWAFで503になるため除去する
        sanitized = brand.replace("'", "").replace("'", "")
        return f"{self.base_url}/{encode_query(sanitized)}/?max={self.config.effective_max_price(brand)}"

    def _card_selectors(self) -> list[str]:
        return ["div.searchresultitem", "div.dui-card.searchresultitem", "[data-item-name]", "div[data-rk-itemid]"]

    def _title_selectors(self) -> list[str]:
        return ["h2.title", ".title--line-clamp", "a[title]", ".content.title"]

    def _price_selectors(self) -> list[str]:
        return [".important", ".price__value", ".price"]

    def _link_selectors(self) -> list[str]:
        return ["a[title]", "a[href]"]

    def _extract_structured_items(self, html: str) -> list[dict]:
        match = re.search(r'"structuredDataCarousel":"(\{.*?\})"', html)
        if not match:
            return []
        try:
            payload = json.loads(f'"{match.group(1)}"')
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
        return data.get("itemListElement", [])

    def search(self, brand: str) -> list[Listing]:
        self.begin_search_stats(brand)
        url = self.build_search_url(brand)
        try:
            html = self.fetch_html_http(url)
            listings: list[Listing] = []
            structured_items = self._extract_structured_items(html)[: self.config.max_items]

            for entry in structured_items:
                item = entry.get("item", {})
                offers = item.get("offers", {})
                listing = self.make_listing(
                    brand,
                    item.get("name", ""),
                    str(offers.get("price", "")),
                    item.get("url", ""),
                    sold=False,
                    metadata={"availability_status": "available"},
                )
                if listing and listing.price <= self.config.effective_max_price(brand):
                    img = item.get("image", "")
                    if isinstance(img, list):
                        listing.image_urls = [u for u in img if isinstance(u, str) and u.startswith("http")]
                    elif isinstance(img, str) and img.startswith("http"):
                        listing.image_urls = [img]
                    listings.append(listing)

            if structured_items:
                self.complete_search_stats(listings, search_result_count=len(structured_items))
                if not listings:
                    logger.warning("[楽天市場] %s の取得件数は0件です", brand)
                return listings

            cards = self.parse_cards(html, self._card_selectors())[: self.config.max_items]
            for card in cards:
                title = self.pick_text(card, self._title_selectors()) or self.pick_attr(card, self._link_selectors(), "title")
                price_text = self.pick_text(card, self._price_selectors())
                item_url = self.pick_attr(card, self._link_selectors(), "href")
                availability_status = detect_availability_status(card.get_text(" ", strip=True))
                imgs = card.select("img")[:3]
                image_urls = [u for img in imgs for u in [img.get("src") or img.get("data-src") or ""] if u.startswith("http")]
                listing = self.make_listing(
                    brand,
                    title,
                    price_text,
                    item_url,
                    sold=False,
                    metadata={"availability_status": availability_status},
                )
                if listing and listing.price <= self.config.effective_max_price(brand):
                    listing.image_urls = image_urls
                    listings.append(listing)

            self.complete_search_stats(listings, search_result_count=len(cards))
            if not listings:
                logger.warning("[楽天市場] %s の取得件数は0件です", brand)
            return listings
        except Exception as error:
            self.fail_search_stats(error)
            logger.warning("[楽天市場] %s の取得に失敗しました: %s", brand, error)
            return []
