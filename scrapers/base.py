from __future__ import annotations

import asyncio
import logging
import queue
import ssl
import threading
from contextlib import AbstractContextManager
from typing import Iterable
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page, async_playwright

from analyzer import Listing
from config import BRAND_ALIASES, DEFAULT_HEADERS, ScraperConfig
from utils import clean_title_text, detect_availability_status, ensure_sleep, extract_price, normalize_text


logger = logging.getLogger(__name__)


class PlaywrightScraper(AbstractContextManager):
    site_name = "unknown"

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.last_search_stats: dict[str, object] = {}

    def __enter__(self) -> "PlaywrightScraper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    def begin_search_stats(self, brand: str) -> None:
        self.last_search_stats = {
            "brand": brand,
            "site_name": self.site_name,
            "search_result_count": 0,
            "detail_page_count": 0,
            "in_stock_count": 0,
            "excluded_count": 0,
            "final_candidate_count": 0,
            "fetch_failed": False,
            "error_message": "",
            "status": "candidate_none",
        }

    def complete_search_stats(
        self,
        listings: list[Listing],
        search_result_count: int,
        detail_page_count: int = 0,
    ) -> None:
        in_stock_count = sum(
            1
            for listing in listings
            if (listing.metadata or {}).get("availability_status", "available") == "available"
        )
        self.last_search_stats.update(
            {
                "search_result_count": search_result_count,
                "detail_page_count": detail_page_count,
                "in_stock_count": in_stock_count,
                "status": "ok" if search_result_count > 0 else "candidate_none",
            }
        )

    def fail_search_stats(self, error: Exception) -> None:
        self.last_search_stats.update(
            {
                "fetch_failed": True,
                "error_message": str(error),
                "status": "fetch_failed",
            }
        )

    def fetch_html(self, url: str) -> str:
        return self.fetch_html_with_options(url)

    def fetch_html_with_options(
        self,
        url: str,
        *,
        goto_timeout_ms: int | None = None,
        wait_until: str | None = None,
        wait_for_selectors: Iterable[str] | None = None,
        selector_timeout_ms: int = 4000,
        retries: int = 0,
    ) -> str:
        logger.info("[%s] fetching %s", self.site_name, url)
        last_error: Exception | None = None
        attempt_count = max(retries, 0) + 1
        for attempt in range(1, attempt_count + 1):
            try:
                return self._run_async_in_thread(
                    self._fetch_html_async(
                        url,
                        goto_timeout_ms=goto_timeout_ms,
                        wait_until=wait_until,
                        wait_for_selectors=list(wait_for_selectors or []),
                        selector_timeout_ms=selector_timeout_ms,
                    )
                )
            except Exception as error:
                last_error = error
                if attempt >= attempt_count:
                    break
                logger.warning("[%s] fetch retry %s/%s for %s: %s", self.site_name, attempt, retries, url, error)
                ensure_sleep(self.config.request_delay_seconds)
        assert last_error is not None
        raise last_error

    def fetch_html_http(self, url: str) -> str:
        logger.info("[%s] fetching %s", self.site_name, url)
        headers = {
            **DEFAULT_HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        request = Request(url, headers=headers)
        ssl_context = ssl._create_unverified_context()
        with urlopen(request, timeout=max(self.config.timeout_ms / 1000, 1), context=ssl_context) as response:
            body = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
        ensure_sleep(self.config.request_delay_seconds)
        return body.decode(encoding, errors="replace")

    def _run_async_in_thread(self, coroutine):
        result_queue: queue.Queue = queue.Queue(maxsize=1)

        def runner() -> None:
            try:
                result_queue.put(("ok", asyncio.run(coroutine)))
            except Exception as error:
                result_queue.put(("error", error))

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        status, payload = result_queue.get()
        if status == "error":
            raise payload
        return payload

    async def _fetch_html_async(
        self,
        url: str,
        *,
        goto_timeout_ms: int | None = None,
        wait_until: str | None = None,
        wait_for_selectors: list[str] | None = None,
        selector_timeout_ms: int = 4000,
    ) -> str:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.config.headless)
            context = await browser.new_context(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="ja-JP",
                ignore_https_errors=True,
            )
            page = await context.new_page()
            page.set_default_timeout(self.config.timeout_ms)
            try:
                await page.goto(
                    url,
                    wait_until=wait_until or self.config.navigation_wait_until,
                    timeout=goto_timeout_ms or self.config.timeout_ms,
                )
                await asyncio.sleep(self.config.request_delay_seconds)
                await self.handle_cookie_banner(page)
                if wait_for_selectors:
                    for selector in wait_for_selectors:
                        try:
                            await page.locator(selector).first.wait_for(state="attached", timeout=selector_timeout_ms)
                            break
                        except Exception:
                            continue
                return await page.content()
            finally:
                await page.close()
                await context.close()
                await browser.close()

    async def handle_cookie_banner(self, page: Page) -> None:
        selectors = [
            "button:has-text('同意')",
            "button:has-text('許可')",
            "button:has-text('Accept')",
            "[data-testid='cookie-accept']",
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count():
                    await locator.click(timeout=1000)
                    await asyncio.sleep(0.4)
                    return
            except Exception:
                continue

    def parse_cards(self, html: str, selectors: Iterable[str]) -> list[Tag]:
        soup = BeautifulSoup(html, "html.parser")
        cards: list[Tag] = []
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        return cards

    def clean_title(self, value: str | None) -> str:
        return clean_title_text(value)

    def brand_matches(self, expected_brand: str, actual_brand: str | None) -> bool:
        actual = self.clean_title(actual_brand)
        if not actual:
            return False
        actual_normalized = normalize_text(actual)
        variants = [normalize_text(expected_brand)] + [normalize_text(a) for a in BRAND_ALIASES.get(expected_brand, [])]
        return any(v in actual_normalized or actual_normalized in v for v in variants)

    def pick_text(self, node: Tag, selectors: Iterable[str]) -> str:
        for selector in selectors:
            target = node.select_one(selector)
            if target and target.get_text(strip=True):
                return self.clean_title(target.get_text(" ", strip=True))
        return ""

    def pick_attr(self, node: Tag, selectors: Iterable[str], attr: str) -> str:
        for selector in selectors:
            target = node.select_one(selector)
            if target and target.get(attr):
                return str(target.get(attr))
        return ""

    def make_listing(
        self,
        brand: str,
        title: str,
        price_text: str,
        url: str,
        sold: bool = False,
        metadata: dict | None = None,
    ) -> Listing | None:
        title = self.clean_title(title)
        price = extract_price(price_text)
        if not title or price is None or price <= 0:
            return None
        normalized_title = normalize_text(title)
        brand_variants = [normalize_text(brand)] + [normalize_text(a) for a in BRAND_ALIASES.get(brand, [])]
        if not any(v in normalized_title for v in brand_variants):
            return None
        payload = dict(metadata or {})
        payload.setdefault("availability_status", detect_availability_status(title))
        return Listing(
            brand=brand,
            title=title,
            price=price,
            url=url,
            site=self.site_name,
            sold=sold,
            metadata=payload,
        )
