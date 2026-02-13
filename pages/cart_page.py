import logging
import re

import allure
from playwright.async_api import Page

from core.base_page import BasePage
from core.locator_utility import ResilientLocator

logger = logging.getLogger(__name__)


class CartPage(BasePage):
    """
    Page Object for eBay shopping cart page.

    Handles opening the cart and reading totals.
    Assertions belong in the test layer (SRP).
    """

    CART_URL = "https://cart.ebay.com"

    # --- Resilient Locators (updated for current eBay layout) ---
    CART_ICON = ResilientLocator("cart_icon", [
        ("css", "a#gh-minicart-hover"),
        ("xpath", "//a[@id='gh-minicart-hover' or contains(@href,'cart.ebay')]"),
    ])

    CART_SUBTOTAL = ResilientLocator("cart_subtotal", [
        ("css", "[data-test-id='SUBTOTAL'] .text-display-span--textDisplaySpan"),
        ("css", "span[class*='text-display-span']"),
    ])

    CART_ITEMS_LIST = ResilientLocator("cart_items_list", [
        ("css", "[data-test-id='cart-item']"),
        ("css", "div[class*='cart-bucket-lineitem']"),
    ])

    @allure.step("Open shopping cart")
    async def open_cart(self) -> bool:
        """
        Navigate directly to the eBay cart page.

        Returns:
            True if cart page loaded successfully, False if captcha blocked access.
        """
        logger.info("Opening shopping cart")
        await self.navigate(self.CART_URL, timeout=60000)
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(3000)
        await self.take_screenshot("cart_opened")

        # Check if we hit a captcha
        current_url = await self.get_current_url()
        if "captcha" in current_url.lower():
            logger.warning("Captcha detected on cart page — cannot verify cart total")
            await self.take_screenshot("cart_captcha_blocked")
            return False

        logger.info(f"Cart page loaded: {current_url}")
        return True

    @allure.step("Get cart total amount")
    async def get_cart_total(self) -> float:
        """
        Read the cart subtotal/total as shown on the cart page.

        Tries multiple strategies to find the total amount.

        Returns:
            Cart total as a float.

        Raises:
            ValueError: If the total cannot be parsed.
        """
        # Strategy 1: Try the resilient locator
        try:
            total_text = await self.get_text(self.CART_SUBTOTAL)
            price = self._parse_price(total_text)
            if price is not None:
                logger.info(f"Cart total: {price:.2f}")
                return price
        except Exception as e:
            logger.warning(f"Primary cart total locator failed: {e}")

        # Strategy 2: Find any element with a dollar/currency amount in the summary area
        try:
            page_text = await self.page.locator("body").text_content(timeout=5000)
            # Look for subtotal pattern
            match = re.search(r"(?:Subtotal|Item subtotal|Total)[^\d]*[\$]?([\d,]+\.?\d*)", page_text, re.IGNORECASE)
            if match:
                price = float(match.group(1).replace(",", ""))
                logger.info(f"Cart total (from page text): {price:.2f}")
                return price
        except Exception as e:
            logger.warning(f"Fallback cart total extraction failed: {e}")

        raise ValueError("Could not parse cart total from page")

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """Extract a numeric price from text."""
        if not text:
            return None
        match = re.search(r"[\$]?([\d,]+\.?\d*)", text)
        if match:
            return float(match.group(1).replace(",", ""))
        return None
