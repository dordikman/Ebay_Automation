import json
import logging
import os

import allure
import pytest

from pages.login_page import LoginPage
from pages.search_results_page import SearchResultsPage
from pages.item_details_page import ItemDetailsPage
from pages.cart_page import CartPage

logger = logging.getLogger(__name__)

# ── Load test data for parametrize ──
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT_DIR, "config", "test_data.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    _test_data = json.load(f)
    TEST_CASES = _test_data["test_cases"]


def _test_id(test_case: dict) -> str:
    """Generate a readable test ID from test case data."""
    return f"{test_case['query']}_max{test_case['max_price']}"


@allure.epic("eBay Automation")
@allure.feature("E2E Shopping Flow")
@pytest.mark.e2e
@pytest.mark.parametrize("test_case", TEST_CASES, ids=[_test_id(tc) for tc in TEST_CASES])
@pytest.mark.asyncio
async def test_ebay_e2e_flow(page, config, test_case):
    """
    Full E2E test scenario:
    1. Login (placeholder — graceful failure)
    2. Search items by name with price filter
    3. Add found items to cart
    4. Assert cart total does not exceed budget
    """
    screenshots_dir = config.get("_run_screenshots_dir", "screenshots")
    query = test_case["query"]
    max_price = test_case["max_price"]
    limit = test_case.get("limit", 5)
    credentials = test_case.get("credentials", {})

    # ── Step 1: Login (stub/guest if placeholder credentials) ──
    with allure.step("Step 1: Login to eBay"):
        login_page = LoginPage(page, screenshots_dir)
        login_success = await login_page.login(
            username=credentials.get("username", ""),
            password=credentials.get("password", "")
        )
        if login_success:
            logger.info("Login succeeded — running as authenticated user")
        else:
            logger.info("Continuing as guest (stub credentials or login failed)")

    # ── Step 2: Search with price filter ──
    with allure.step(f"Step 2: Search '{query}' under ${max_price}"):
        search_page = SearchResultsPage(page, screenshots_dir)
        urls = await search_page.search_items_by_name_under_price(
            query=query,
            max_price=max_price,
            limit=limit
        )
        logger.info(f"Found {len(urls)} items for '{query}' under ${max_price}")

        # Assertion: search returned at least one qualifying item
        assert len(urls) > 0, (
            f"No items found for query='{query}' under ${max_price}. "
            f"Expected at least 1 item."
        )
        # Assertion: did not exceed the requested limit
        assert len(urls) <= limit, (
            f"Returned {len(urls)} URLs, exceeds requested limit={limit}"
        )

    # ── Step 3: Add items to cart ──
    with allure.step(f"Step 3: Add {len(urls)} items to cart"):
        added_count = await add_items_to_cart(page, urls, screenshots_dir)

        # Assertion: at least one item was successfully added to cart
        assert added_count > 0, (
            f"Failed to add any items to cart out of {len(urls)} URLs"
        )
        logger.info(f"Successfully added {added_count}/{len(urls)} items to cart")

    # ── Step 4: Assert cart total does not exceed budget ──
    with allure.step(f"Step 4: Assert cart total <= ${max_price} x {added_count}"):
        cart_page = CartPage(page, screenshots_dir)
        await assert_cart_total_not_exceeds(cart_page, max_price, added_count)


async def assert_cart_total_not_exceeds(cart_page: CartPage,
                                        budget_per_item: float,
                                        items_count: int):
    """
    Open the cart and assert that the total does not exceed the allowed budget.

    Budget = budget_per_item * items_count.
    Page Object (CartPage) only returns data; the assertion lives here in the test layer.

    Args:
        cart_page: CartPage instance.
        budget_per_item: Maximum price per item.
        items_count: Number of items added to cart.
    """
    cart_loaded = await cart_page.open_cart()

    if not cart_loaded:
        pytest.skip("Cart page blocked by captcha — cannot verify total")

    cart_total = await cart_page.get_cart_total()
    max_budget = budget_per_item * items_count

    logger.info(
        f"Cart assertion: total={cart_total:.2f}, "
        f"budget={max_budget:.2f} ({budget_per_item} x {items_count})"
    )

    assert cart_total <= max_budget, (
        f"Cart total {cart_total:.2f} exceeds budget {max_budget:.2f} "
        f"({budget_per_item} x {items_count} items)"
    )

    logger.info(f"Cart total {cart_total:.2f} is within budget {max_budget:.2f}")


async def add_items_to_cart(page, urls: list[str],
                            screenshots_dir: str = "screenshots") -> int:
    """
    Add items to cart by navigating to each URL.

    For each item:
    - Opens the item page
    - Selects random variants if needed (size/color)
    - Clicks "Add to cart"
    - Logs and takes a screenshot

    Args:
        page: Playwright Page object.
        urls: List of item URLs to add.
        screenshots_dir: Directory for screenshots.

    Returns:
        Number of items successfully added to cart.
    """
    item_page = ItemDetailsPage(page, screenshots_dir)
    added_count = 0

    for i, url in enumerate(urls, start=1):
        with allure.step(f"Adding item {i}/{len(urls)}: {url}"):
            logger.info(f"Adding item {i}/{len(urls)}: {url}")

            try:
                await item_page.navigate(url)

                # Select random variants if the item requires them
                await item_page.select_random_variants()

                # Add to cart
                success = await item_page.add_to_cart()

                if success:
                    added_count += 1
                    logger.info(f"Item {i} added to cart successfully")
                else:
                    logger.warning(f"Item {i} could not be added to cart")

            except Exception as e:
                logger.error(f"Failed to process item {i} ({url}): {e}")
                await item_page.take_screenshot(f"item_{i}_error")

    logger.info(f"Add to cart summary: {added_count}/{len(urls)} items added")
    return added_count
