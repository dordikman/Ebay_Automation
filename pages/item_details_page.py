import logging
import random
import re

import allure
from playwright.async_api import Page

from core.base_page import BasePage
from core.locator_utility import ResilientLocator
from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class ItemDetailsPage(BasePage):
    """
    Page Object for eBay item details page.

    Handles variant selection (size, color, quantity), adding items to cart,
    and extracting item price.
    """

    # --- Resilient Locators (updated for current eBay layout) ---
    ITEM_PRICE = ResilientLocator("item_price", [
        ("css", "[data-testid='x-price-primary']"),
        ("xpath", "//div[contains(@class,'x-price-primary')]//span"),
    ])

    ADD_TO_CART_BTN = ResilientLocator("add_to_cart_button", [
        ("css", "#atcBtn_btn_1"),
        ("css", "a:has-text('Add to cart')"),
    ])

    # New eBay uses listbox-based selectors (not <select>)
    VARIANT_LISTBOX = ResilientLocator("variant_listbox", [
        ("css", "[data-testid='x-msku-evo'] .listbox-button__button"),
        ("xpath", "//div[@data-testid='x-msku-evo']//button[contains(@class,'listbox-button')]"),
    ])

    VARIANT_OPTIONS = ResilientLocator("variant_options", [
        ("css", "[data-testid='x-msku-evo'] .listbox__option:not([aria-disabled='true'])"),
        ("xpath", "//div[@data-testid='x-msku-evo']//div[contains(@class,'listbox__option') and not(@aria-disabled='true')]"),
    ])

    QUANTITY_INPUT = ResilientLocator("quantity_input", [
        ("css", "input#qtyTextBox"),
        ("xpath", "//input[@id='qtyTextBox' or @name='quantity']"),
    ])

    @allure.step("Select random variants if required")
    async def select_random_variants(self):
        """
        Select random available variants (size, color) if the item requires it.

        eBay now uses listbox-based variant selectors. This method clicks the
        listbox button to open it, then picks a random available option.
        Graceful — does not fail if no variants exist.
        """
        try:
            # Check if variant selector exists
            variant_buttons = self.page.locator(
                "[data-testid='x-msku-evo'] .listbox-button__button"
            )
            count = await variant_buttons.count()

            if count == 0:
                logger.info("No variant selectors found — skipping")
                return

            # Click each variant listbox and select a random option
            for i in range(count):
                await self._select_variant_option(variant_buttons.nth(i), i)
                await self.page.wait_for_timeout(1000)

        except Exception as e:
            logger.warning(f"Could not select variants: {e}")

    async def _select_variant_option(self, listbox_button, index: int):
        """Open a variant listbox and select a random available option."""
        try:
            # Click to open the listbox
            await listbox_button.click(timeout=5000)
            await self.page.wait_for_timeout(500)

            # Find available (non-disabled) options
            options = self.page.locator(
                "[data-testid='x-msku-evo'] .listbox__option:not([aria-disabled='true'])"
            )
            options_count = await options.count()

            if options_count > 0:
                random_idx = random.randint(0, options_count - 1)
                option = options.nth(random_idx)
                option_text = await option.text_content(timeout=3000)
                await option.click(timeout=5000)
                logger.info(f"Variant {index}: selected '{option_text}' (option {random_idx}/{options_count})")
                await self.page.wait_for_timeout(500)
            else:
                logger.info(f"Variant {index}: no available options")
                # Click away to close the listbox
                await self.page.keyboard.press("Escape")

        except Exception as e:
            logger.warning(f"Could not select variant {index}: {e}")
            await self.page.keyboard.press("Escape")

    @allure.step("Get item price")
    async def get_price(self) -> float:
        """
        Extract the item price from the details page.

        Returns:
            Item price as a float.

        Raises:
            ValueError: If price cannot be extracted.
        """
        price_text = await self.get_text(self.ITEM_PRICE)
        match = re.search(r"\$?([\d,]+\.?\d*)", price_text)
        if match:
            price = float(match.group(1).replace(",", ""))
            logger.info(f"Item price: ${price:.2f}")
            return price
        raise ValueError(f"Could not extract price from text: '{price_text}'")

    async def add_to_cart(self) -> bool:
        """
        Click "Add to cart" button with retry + backoff.

        Returns:
            True if add to cart was clicked successfully, False otherwise.
        """
        with allure.step("Add item to cart"):
            try:
                await self._click_add_to_cart()
                logger.info("Add to cart clicked successfully")
                await self.take_screenshot("item_added_to_cart")
                return True
            except Exception as e:
                logger.error(f"Failed to add item to cart after retries: {e}")
                await self.take_screenshot("add_to_cart_failure")
                return False

    @retry_with_backoff(max_retries=3, base_delay=1.0, backoff_factor=2.0)
    async def _click_add_to_cart(self):
        """Internal: click the Add to Cart button. Raises on failure so retry can work."""
        add_btn = await self.find_element(self.ADD_TO_CART_BTN)
        await add_btn.click(force=True, timeout=15000)
        await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        await self.page.wait_for_timeout(2000)
