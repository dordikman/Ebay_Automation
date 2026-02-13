import logging
import re

import allure
from playwright.async_api import Page

from core.base_page import BasePage
from core.locator_utility import ResilientLocator

logger = logging.getLogger(__name__)


class SearchResultsPage(BasePage):
    """
    Page Object for eBay search and results page.

    Handles searching for items, applying price filters, collecting item URLs
    with pagination support.
    """

    URL = "https://www.ebay.com"

    # --- Resilient Locators (updated for current eBay layout) ---
    SEARCH_INPUT = ResilientLocator("search_input", [
        ("css", "#gh-ac"),
        ("xpath", "//input[@id='gh-ac']"),
    ])

    SEARCH_BUTTON = ResilientLocator("search_button", [
        ("css", "#gh-search-btn"),
        ("xpath", "//button[@type='submit' and @id='gh-search-btn']"),
    ])

    PRICE_MIN_INPUT = ResilientLocator("price_min_input", [
        ("css", "input[aria-label*='Minimum']"),
        ("xpath", "//input[contains(@aria-label,'Minimum')]"),
    ])

    PRICE_MAX_INPUT = ResilientLocator("price_max_input", [
        ("css", "input[aria-label*='Maximum']"),
        ("xpath", "//input[contains(@aria-label,'Maximum')]"),
    ])

    PRICE_SUBMIT_BTN = ResilientLocator("price_submit_button", [
        ("css", "button[aria-label*='Submit price range']"),
        ("xpath", "//button[contains(@aria-label,'Submit price range')]"),
    ])

    RESULT_ITEMS = ResilientLocator("result_items", [
        ("css", "ul.srp-results > li.s-card"),
        ("xpath", "//ul[contains(@class,'srp-results')]/li[contains(@class,'s-card')]"),
    ])

    NEXT_PAGE_BTN = ResilientLocator("next_page_button", [
        ("css", "a.pagination__next"),
        ("xpath", "//a[contains(@class,'pagination__next')]"),
    ])

    @allure.step("Search for: {query}")
    async def search(self, query: str):
        """
        Perform a search on eBay using Enter key.

        Args:
            query: Search term (e.g., 'shoes').
        """
        logger.info(f"Searching for: '{query}'")
        await self.navigate(self.URL)
        await self.fill(self.SEARCH_INPUT, query)

        # Use Enter key — more reliable than clicking the search button
        search_input = await self.find_element(self.SEARCH_INPUT)
        await search_input.press("Enter")

        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(3000)
        await self.take_screenshot(f"search_results_{query}")
        logger.info(f"Search completed for: '{query}'")

    @allure.step("Apply price filter: max {max_price}")
    async def apply_price_filter(self, max_price: float):
        """
        Apply price filter on the search results page.

        Uses the price range inputs if available. If the filter elements
        are not found, logs a warning and continues without filtering.

        Args:
            max_price: Maximum price to filter by.
        """
        try:
            logger.info(f"Applying price filter: max {max_price}")

            # The price inputs are inside span wrappers — target the actual input
            min_input = await self.find_element(self.PRICE_MIN_INPUT)
            await min_input.fill("")
            await min_input.type("0")

            max_input = await self.find_element(self.PRICE_MAX_INPUT)
            await max_input.fill("")
            await max_input.type(str(int(max_price)))

            await self.click(self.PRICE_SUBMIT_BTN)
            await self.page.wait_for_load_state("domcontentloaded")
            await self.page.wait_for_timeout(3000)
            await self.take_screenshot(f"price_filter_applied_{max_price}")
            logger.info(f"Price filter applied: 0 - {max_price}")
        except Exception as e:
            logger.warning(f"Could not apply price filter: {e}. Continuing without filter.")

    @allure.step("Collect up to {limit} items under {max_price}")
    async def get_items_under_price(self, max_price: float, limit: int = 5) -> list[str]:
        """
        Collect item URLs from search results where price <= max_price.

        Iterates through result items, extracts price and URL. Supports
        pagination — if fewer than `limit` items found on current page,
        navigates to next page and continues collecting.

        Args:
            max_price: Maximum price threshold.
            limit: Maximum number of items to collect.

        Returns:
            List of item URLs (up to `limit`) that meet the price condition.
        """
        collected_urls: list[str] = []
        max_pages = 5  # Safety limit to prevent infinite pagination

        for page_num in range(1, max_pages + 1):
            logger.info(f"Scanning page {page_num} for items under {max_price}")

            try:
                items_locator = await self.find_elements(self.RESULT_ITEMS, timeout=10000)
                items_count = await items_locator.count()
                logger.info(f"Found {items_count} items on page {page_num}")
            except Exception:
                logger.warning(f"No items found on page {page_num}")
                break

            for i in range(items_count):
                if len(collected_urls) >= limit:
                    break

                item = items_locator.nth(i)
                try:
                    price = await self._extract_item_price(item)
                    url = await self._extract_item_url(item)

                    if price is None or url is None:
                        continue

                    if price <= max_price:
                        collected_urls.append(url)
                        logger.info(
                            f"Item {len(collected_urls)}/{limit}: {price:.2f} — {url[:80]}"
                        )
                except Exception as e:
                    logger.debug(f"Skipping item {i} on page {page_num}: {e}")
                    continue

            if len(collected_urls) >= limit:
                break

            # Try pagination
            if not await self._go_to_next_page():
                logger.info("No more pages available")
                break

        logger.info(f"Collected {len(collected_urls)} items under {max_price}")
        await self.take_screenshot(f"collected_{len(collected_urls)}_items")
        return collected_urls

    async def search_items_by_name_under_price(self, query: str, max_price: float,
                                                limit: int = 5) -> list[str]:
        """
        Main function: search for items and return URLs of those under max_price.

        Combines search, price filter, and item collection.

        Args:
            query: Search term.
            max_price: Maximum price per item.
            limit: Maximum number of item URLs to return.

        Returns:
            List of up to `limit` item URLs with price <= max_price.
        """
        with allure.step(f"searchItemsByNameUnderPrice('{query}', {max_price}, {limit})"):
            await self.search(query)
            await self.apply_price_filter(max_price)
            urls = await self.get_items_under_price(max_price, limit)
            logger.info(
                f"searchItemsByNameUnderPrice result: {len(urls)} URLs for "
                f"query='{query}', maxPrice={max_price}"
            )
            return urls

    async def _extract_item_price(self, item) -> float | None:
        """Extract price from a search result item element."""
        try:
            # New eBay layout uses [class*=price] for price display
            price_el = item.locator("[class*=price]").first
            price_text = await price_el.text_content(timeout=3000)
            if not price_text:
                return None

            # Handle multiple currencies: $10.00, ILS 10.00, EUR 10.00
            # Also handle ranges like "$10.00 to $20.00" — take the first price
            match = re.search(r"[\$]?([\d,]+\.?\d*)", price_text)
            if match:
                return float(match.group(1).replace(",", ""))
            return None
        except Exception:
            return None

    async def _extract_item_url(self, item) -> str | None:
        """Extract URL from a search result item element."""
        try:
            link = item.locator("a[href*='/itm/']").first
            href = await link.get_attribute("href", timeout=3000)
            return href
        except Exception:
            return None

    async def _go_to_next_page(self) -> bool:
        """Navigate to the next page of results. Returns False if no next page."""
        try:
            if await self.is_element_visible(self.NEXT_PAGE_BTN, timeout=3000):
                await self.click(self.NEXT_PAGE_BTN)
                await self.page.wait_for_load_state("domcontentloaded")
                await self.page.wait_for_timeout(3000)
                logger.info("Navigated to next page")
                return True
            return False
        except Exception:
            return False
