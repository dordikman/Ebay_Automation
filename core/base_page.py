import asyncio
import logging

import allure
from playwright.async_api import Page, Locator

from core.locator_utility import ResilientLocator
from utils.screenshot import capture_screenshot

MAX_NAV_RETRIES = 3
NAV_BACKOFF_BASE = 1.0
NAV_BACKOFF_FACTOR = 2.0

logger = logging.getLogger(__name__)


class BasePage:
    

    def __init__(self, page: Page, screenshots_dir: str = "screenshots",
                 default_timeout: int = 10000):
        self.page = page
        self.screenshots_dir = screenshots_dir
        self.default_timeout = default_timeout

    async def find_element(self, resilient_locator: ResilientLocator,
                           timeout: int = None) -> Locator:
        """Find a single element using resilient locator with fallback."""
        timeout = timeout or self.default_timeout
        return await resilient_locator.find(self.page, timeout, self.screenshots_dir)

    async def find_elements(self, resilient_locator: ResilientLocator,
                            timeout: int = None) -> Locator:
        """Find all matching elements using resilient locator with fallback."""
        timeout = timeout or self.default_timeout
        return await resilient_locator.find_all(self.page, timeout, self.screenshots_dir)

    async def click(self, resilient_locator: ResilientLocator, timeout: int = None):
        """Click an element with resilient locator fallback."""
        with allure.step(f"Click on '{resilient_locator.name}'"):
            element = await self.find_element(resilient_locator, timeout)
            await element.click()
            logger.info(f"Clicked on '{resilient_locator.name}'")

    async def fill(self, resilient_locator: ResilientLocator, text: str,
                   timeout: int = None):
        """Fill an input field with resilient locator fallback."""
        with allure.step(f"Fill '{resilient_locator.name}' with text"):
            element = await self.find_element(resilient_locator, timeout)
            await element.fill(text)
            logger.info(f"Filled '{resilient_locator.name}' with '{text}'")

    async def get_text(self, resilient_locator: ResilientLocator,
                       timeout: int = None) -> str:
        """Get text content of an element with resilient locator fallback."""
        with allure.step(f"Get text from '{resilient_locator.name}'"):
            element = await self.find_element(resilient_locator, timeout)
            text = await element.text_content()
            logger.info(f"Got text from '{resilient_locator.name}': '{text}'")
            return text or ""

    async def wait_for_element(self, resilient_locator: ResilientLocator,
                               state: str = "visible", timeout: int = None):
        """Wait for an element to reach a given state."""
        with allure.step(f"Wait for '{resilient_locator.name}' to be {state}"):
            element = await self.find_element(resilient_locator, timeout)
            await element.wait_for(state=state, timeout=timeout or self.default_timeout)
            logger.info(f"Element '{resilient_locator.name}' reached state '{state}'")

    async def navigate(self, url: str, timeout: int = 60000):
        """Navigate to a URL with retry + exponential backoff."""
        with allure.step(f"Navigate to {url}"):
            last_error = None
            for attempt in range(1, MAX_NAV_RETRIES + 1):
                try:
                    logger.info(f"Navigating to: {url} (attempt {attempt}/{MAX_NAV_RETRIES})")
                    await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                    logger.info(f"Navigation complete: {url}")
                    return
                except Exception as e:
                    last_error = e
                    if attempt < MAX_NAV_RETRIES:
                        delay = NAV_BACKOFF_BASE * (NAV_BACKOFF_FACTOR ** (attempt - 1))
                        logger.warning(
                            f"Navigation attempt {attempt}/{MAX_NAV_RETRIES} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Navigation failed after {MAX_NAV_RETRIES} attempts: {e}")
            raise last_error

    async def take_screenshot(self, name: str) -> str:
        """Capture a screenshot and attach to Allure report."""
        return await capture_screenshot(self.page, name, self.screenshots_dir)

    async def is_element_visible(self, resilient_locator: ResilientLocator,
                                 timeout: int = 3000) -> bool:
        """Check if an element is visible without raising on failure."""
        try:
            element = await self.find_element(resilient_locator, timeout)
            return await element.is_visible()
        except Exception:
            return False

    async def get_current_url(self) -> str:
        """Return the current page URL."""
        return self.page.url
