import logging

import allure
from playwright.async_api import Page, Locator

from utils.screenshot import capture_screenshot

logger = logging.getLogger(__name__)


class ResilientLocator:
    """
    Manages multiple alternative locators for a single UI element.

    Each element has at least two locator strategies. At runtime, if the primary
    locator fails, the system automatically tries the next alternative.
    The number of attempts equals the number of defined locators.

    Logging: Every attempt is logged (success/failure, strategy, attempt count).
    Allure: Each locator resolution is wrapped in an Allure step for report visibility.
    Screenshot: Taken on final failure before raising.
    """

    def __init__(self, name: str, locators: list[tuple[str, str]]):
        if len(locators) < 2:
            raise ValueError(
                f"ResilientLocator '{name}' requires at least 2 locators, got {len(locators)}"
            )
        self.name = name
        self.locators = locators

    async def find(self, page: Page, timeout: int = 10000,
                   screenshots_dir: str = "screenshots") -> Locator:
        """
        Attempt to find the element using each locator in order.

        Tries each locator strategy sequentially. Logs and reports
        success/failure for each attempt via logger + Allure step.
        Takes a screenshot on final failure before raising.
        """
        last_exception = None

        with allure.step(f"Find element '{self.name}' ({len(self.locators)} strategies)"):
            for attempt, (strategy, value) in enumerate(self.locators, start=1):
                try:
                    locator = self._get_locator(page, strategy, value)
                    await locator.first.wait_for(state="attached", timeout=timeout)

                    msg = (f"[{self.name}] Locator SUCCESS - strategy='{strategy}', "
                           f"value='{value}', attempt={attempt}/{len(self.locators)}")
                    logger.info(msg)
                    allure.attach(msg, name=f"{self.name} - attempt {attempt} SUCCESS",
                                  attachment_type=allure.attachment_type.TEXT)
                    return locator.first

                except Exception as e:
                    last_exception = e
                    msg = (f"[{self.name}] Locator FAILED - strategy='{strategy}', "
                           f"value='{value}', attempt={attempt}/{len(self.locators)}, "
                           f"error={e}")
                    logger.warning(msg)
                    allure.attach(msg, name=f"{self.name} - attempt {attempt} FAILED",
                                  attachment_type=allure.attachment_type.TEXT)

            # All locators failed — capture screenshot and raise
            logger.error(
                f"[{self.name}] All {len(self.locators)} locator attempts FAILED. "
                f"Taking failure screenshot."
            )
            await capture_screenshot(page, f"locator_failure_{self.name}", screenshots_dir)
            raise Exception(
                f"Element '{self.name}' not found after {len(self.locators)} attempts. "
                f"Last error: {last_exception}"
            )

    async def find_all(self, page: Page, timeout: int = 10000,
                       screenshots_dir: str = "screenshots") -> Locator:
        """
        Find all matching elements using the first successful locator strategy.

        Returns the Locator (which may match multiple elements) rather than .first.
        """
        last_exception = None

        with allure.step(f"Find all '{self.name}' ({len(self.locators)} strategies)"):
            for attempt, (strategy, value) in enumerate(self.locators, start=1):
                try:
                    locator = self._get_locator(page, strategy, value)
                    await locator.first.wait_for(state="attached", timeout=timeout)

                    count = await locator.count()
                    msg = (f"[{self.name}] find_all SUCCESS - strategy='{strategy}', "
                           f"value='{value}', found={count} elements, "
                           f"attempt={attempt}/{len(self.locators)}")
                    logger.info(msg)
                    allure.attach(msg, name=f"{self.name} - attempt {attempt} SUCCESS",
                                  attachment_type=allure.attachment_type.TEXT)
                    return locator

                except Exception as e:
                    last_exception = e
                    msg = (f"[{self.name}] find_all FAILED - strategy='{strategy}', "
                           f"value='{value}', attempt={attempt}/{len(self.locators)}, "
                           f"error={e}")
                    logger.warning(msg)
                    allure.attach(msg, name=f"{self.name} - attempt {attempt} FAILED",
                                  attachment_type=allure.attachment_type.TEXT)

            logger.error(
                f"[{self.name}] find_all - All {len(self.locators)} attempts FAILED."
            )
            await capture_screenshot(page, f"locator_failure_{self.name}", screenshots_dir)
            raise Exception(
                f"Elements '{self.name}' not found after {len(self.locators)} attempts. "
                f"Last error: {last_exception}"
            )

    @staticmethod
    def _get_locator(page: Page, strategy: str, value: str) -> Locator:
        """Map strategy string to Playwright locator method."""
        strategy = strategy.lower()
        if strategy == "css":
            return page.locator(value)
        elif strategy == "xpath":
            return page.locator(f"xpath={value}")
        elif strategy == "text":
            return page.get_by_text(value)
        elif strategy == "role":
            return page.get_by_role(value)
        elif strategy == "test_id":
            return page.get_by_test_id(value)
        else:
            raise ValueError(f"Unknown locator strategy: '{strategy}'")

    def __repr__(self) -> str:
        strategies = [f"{s}={v}" for s, v in self.locators]
        return f"ResilientLocator('{self.name}', [{', '.join(strategies)}])"
