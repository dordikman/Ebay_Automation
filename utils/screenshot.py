import os
import logging
from datetime import datetime

import allure
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def capture_screenshot(page: Page, name: str, folder: str = "screenshots") -> str:
    """
    Capture a screenshot and attach it to the Allure report.

    Args:
        page: Playwright Page object.
        name: Descriptive name for the screenshot.
        folder: Directory to save screenshots.

    Returns:
        Path to the saved screenshot.
    """
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = name.replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_{timestamp}.png"
    filepath = os.path.join(folder, filename)

    await page.screenshot(path=filepath, full_page=True)
    logger.info(f"Screenshot saved: {filepath}")

    allure.attach.file(
        filepath,
        name=name,
        attachment_type=allure.attachment_type.PNG
    )

    return filepath
