import logging

import allure
from playwright.async_api import Page

from core.base_page import BasePage
from core.locator_utility import ResilientLocator

logger = logging.getLogger(__name__)

# Placeholder credentials that indicate "no real account"
_PLACEHOLDER_USERS = {"", "test_user", "test", "placeholder"}


class LoginPage(BasePage):
    """
    Page Object for eBay login page.

    Supports two modes:
    - **Stub/guest mode**: When credentials are placeholder or empty, navigates
      directly to eBay homepage without wasting time on the login form.
    - **Real login mode**: When real credentials are provided, attempts the full
      login flow (username -> continue -> password -> sign in) with graceful failure
      handling for captcha/2FA.

    In both cases the function returns True/False and never crashes the test.
    """

    LOGIN_URL = "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn"
    HOME_URL = "https://www.ebay.com"

    # --- Resilient Locators (2+ alternatives per element) ---
    USERNAME_INPUT = ResilientLocator("username_input", [
        ("css", "#userid"),
        ("xpath", "//input[@name='userid' or @id='userid']"),
    ])

    CONTINUE_BTN = ResilientLocator("continue_button", [
        ("css", "#signin-continue-btn"),
        ("xpath", "//button[@id='signin-continue-btn']"),
    ])

    PASSWORD_INPUT = ResilientLocator("password_input", [
        ("css", "#pass"),
        ("xpath", "//input[@name='pass' or @id='pass']"),
    ])

    SIGN_IN_BTN = ResilientLocator("sign_in_button", [
        ("css", "#sgnBt"),
        ("xpath", "//button[@id='sgnBt']"),
    ])

    @allure.step("Login to eBay")
    async def login(self, username: str, password: str) -> bool:
        """
        Attempt to login to eBay, or continue as guest if credentials are placeholders.

        Args:
            username: eBay account username/email.
            password: eBay account password.

        Returns:
            True if login succeeded, False if skipped or failed.
        """
        if self._is_placeholder(username):
            return await self._guest_flow()

        return await self._real_login_flow(username, password)

    async def _guest_flow(self) -> bool:
        """Navigate to eBay homepage as guest (stub credentials)."""
        with allure.step("Guest flow — no real credentials provided"):
            logger.info("Credentials are placeholder — skipping login, continuing as guest")
            await self.navigate(self.HOME_URL)
            await self.page.wait_for_load_state("domcontentloaded")
            await self.take_screenshot("login_skipped_guest_mode")

            allure.attach(
                "Login skipped: placeholder credentials detected. Continuing as guest.",
                name="Login mode: GUEST",
                attachment_type=allure.attachment_type.TEXT,
            )
            return False

    async def _real_login_flow(self, username: str, password: str) -> bool:
        """Attempt full login with real credentials. Graceful on captcha/2FA."""
        with allure.step(f"Real login attempt for user: {username}"):
            try:
                logger.info(f"Attempting login for user: {username}")
                await self.navigate(self.LOGIN_URL)

                # Step 1: Enter username
                await self.fill(self.USERNAME_INPUT, username)
                await self.take_screenshot("login_username_entered")

                # Step 2: Click "Continue" (eBay uses a 2-step login form)
                if await self.is_element_visible(self.CONTINUE_BTN, timeout=3000):
                    await self.click(self.CONTINUE_BTN)
                    await self.page.wait_for_timeout(1500)

                # Step 3: Enter password
                await self.fill(self.PASSWORD_INPUT, password)
                await self.take_screenshot("login_password_entered")

                # Step 4: Click "Sign in"
                await self.click(self.SIGN_IN_BTN)
                await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                await self.take_screenshot("login_result")

                # Check outcome
                current_url = await self.get_current_url()
                if "signin" not in current_url.lower():
                    logger.info("Login succeeded")
                    allure.attach(
                        f"Login successful for user: {username}",
                        name="Login: SUCCESS",
                        attachment_type=allure.attachment_type.TEXT,
                    )
                    return True

                # Still on sign-in page -> captcha / 2FA / wrong credentials
                logger.warning("Login failed — still on sign-in page (captcha/2FA?)")
                await self.take_screenshot("login_failed_captcha")

            except Exception as e:
                logger.warning(f"Login failed gracefully: {e}")
                await self.take_screenshot("login_failure")

            # Ensure browser is on homepage so subsequent steps work cleanly
            await self._navigate_to_homepage()
            return False

    async def _navigate_to_homepage(self):
        """Navigate to eBay homepage after a failed login to leave a clean state."""
        try:
            logger.info("Navigating to eBay homepage after login failure")
            await self.navigate(self.HOME_URL)
            await self.page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            logger.warning(f"Could not navigate to homepage: {e}")

    @staticmethod
    def _is_placeholder(username: str) -> bool:
        """Check if credentials are stub/placeholder values."""
        return (username or "").strip().lower() in _PLACEHOLDER_USERS
