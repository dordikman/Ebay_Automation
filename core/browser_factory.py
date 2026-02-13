import json
import logging
import urllib.request

from playwright.async_api import async_playwright, Browser, Playwright

logger = logging.getLogger(__name__)


class BrowserFactory:
    """
    Creates Playwright browser instances for local or remote (Selenoid Grid) execution.

    Local mode: launches a browser directly via Playwright.
    Grid mode:  creates a WebDriver session on Selenoid, extracts the CDP WebSocket
                URL from the session response, and connects Playwright via CDP.
    """

    def __init__(self, config: dict):
        self.config = config
        self._playwright: Playwright = None
        self._selenoid_session_id: str = None
        self._grid_http_url: str = None

    async def create_browser(self, browser_name: str = "chromium",
                              channel: str = None) -> Browser:
        """
        Create a browser instance based on config (local or Grid).

        Args:
            browser_name: Playwright browser name (chromium, firefox, webkit).
            channel: Browser channel (e.g. 'chrome' for branded Chrome).

        Returns:
            Playwright Browser instance.
        """
        self._playwright = await async_playwright().start()

        grid_config = self.config.get("grid", {})
        if grid_config.get("enabled", False) and grid_config.get("url"):
            logger.info(f"Creating remote browser via Selenoid Grid: {browser_name}")
            return await self._create_remote_browser(browser_name, grid_config)
        else:
            logger.info(f"Creating local browser: {browser_name} (channel={channel})")
            return await self._create_local_browser(browser_name, channel)

    async def _create_local_browser(self, browser_name: str,
                                     channel: str = None) -> Browser:
        """Launch a local Playwright browser."""
        headless = self.config.get("headless", False)
        launch_opts = {"headless": headless}
        if channel:
            launch_opts["channel"] = channel

        browser_type = getattr(self._playwright, browser_name, self._playwright.chromium)
        browser = await browser_type.launch(**launch_opts)
        logger.info(f"Local browser launched: {browser_name} (headless={headless})")
        return browser

    async def _create_remote_browser(self, browser_name: str,
                                      grid_config: dict) -> Browser:
        """
        Create a remote browser session via Selenoid Grid + CDP.

        Flow:
        1. POST /wd/hub/session → create WebDriver session on Selenoid
        2. Extract se:cdp WebSocket URL from response
        3. Connect Playwright via connect_over_cdp()
        """
        grid_url = grid_config["url"].rstrip("/")
        self._grid_http_url = grid_url

        # Map Playwright browser names to WebDriver browser names
        wd_browser_map = {
            "chromium": "chrome",
            "chrome": "chrome",
            "firefox": "firefox",
            "webkit": "chrome",
            "edge": "MicrosoftEdge",
        }
        wd_browser_name = wd_browser_map.get(browser_name.lower(), "chrome")

        # Build WebDriver capabilities for Selenoid
        capabilities = {
            "capabilities": {
                "alwaysMatch": {
                    "browserName": wd_browser_name,
                    "selenoid:options": {
                        "enableVNC": True,
                        "enableLog": True,
                        "enableVideo": False,
                    }
                }
            }
        }

        session_url = f"{grid_url}/session"
        logger.info(f"Creating Selenoid session: {session_url} (browser={wd_browser_name})")

        req = urllib.request.Request(
            session_url,
            data=json.dumps(capabilities).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                session_value = data["value"]
                self._selenoid_session_id = session_value["sessionId"]
                cdp_ws_url = session_value.get("capabilities", {}).get("se:cdp", "")
                logger.info(
                    f"Selenoid session created: id={self._selenoid_session_id}, "
                    f"cdp={cdp_ws_url}"
                )
        except Exception as e:
            raise ConnectionError(
                f"Failed to create Selenoid session at {session_url}: {e}"
            )

        # Fallback: construct CDP URL if not provided in response
        if not cdp_ws_url:
            host_port = grid_url.replace("http://", "").replace("https://", "").split("/")[0]
            cdp_ws_url = f"ws://{host_port}/devtools/{self._selenoid_session_id}"
            logger.info(f"Using fallback CDP URL: {cdp_ws_url}")

        # Connect Playwright to the remote browser via CDP
        browser = await self._playwright.chromium.connect_over_cdp(cdp_ws_url)
        logger.info("Playwright connected to Selenoid via CDP")
        return browser

    async def cleanup(self):
        """Clean up: delete Selenoid session and stop Playwright."""
        if self._selenoid_session_id and self._grid_http_url:
            try:
                delete_url = f"{self._grid_http_url}/session/{self._selenoid_session_id}"
                logger.info(f"Deleting Selenoid session: {self._selenoid_session_id}")
                req = urllib.request.Request(delete_url, method="DELETE")
                urllib.request.urlopen(req, timeout=10)
                logger.info("Selenoid session deleted successfully")
            except Exception as e:
                logger.warning(f"Could not delete Selenoid session: {e}")
            self._selenoid_session_id = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
