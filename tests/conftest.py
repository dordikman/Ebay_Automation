import json
import os
from datetime import datetime

import allure
import pytest
import pytest_asyncio
import yaml

from core.browser_factory import BrowserFactory
from utils.logger import setup_logger

logger = setup_logger("ebay_automation")

# ── Project root ──
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Load config at module level (needed for browser parametrize) ──
_config_path = os.path.join(ROOT_DIR, "config", "config.yaml")
with open(_config_path, "r", encoding="utf-8") as f:
    _raw_config = yaml.safe_load(f)

# ── Browser matrix ──
# Determine which browsers to test based on grid mode.
# Selenoid Grid supports Chrome via CDP only.
# Local mode supports all Playwright browsers (chromium, firefox, webkit).
_BROWSERS = _raw_config.get("browsers", [{"name": "chromium"}])
if _raw_config.get("grid", {}).get("enabled", False):
    _BROWSERS = [b for b in _BROWSERS if b.get("name") in ("chromium", "chrome")]
    if not _BROWSERS:
        _BROWSERS = [{"name": "chromium", "channel": "chrome"}]


# ── Unique report directories per run ──

def pytest_configure(config):
    """
    Set unique report directories per run (timestamp-based).

    Each run generates:
    - reports/TIMESTAMP/allure-results/  (Allure raw data)
    - reports/TIMESTAMP/report.html      (pytest-html)
    - reports/TIMESTAMP/junit-report.xml (JUnit XML)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(ROOT_DIR, "reports", timestamp)
    os.makedirs(run_dir, exist_ok=True)

    # Allure results → reports/TIMESTAMP/allure-results/
    allure_dir = os.path.join(run_dir, "allure-results")
    os.makedirs(allure_dir, exist_ok=True)
    config.option.allure_report_dir = allure_dir

    # JUnit XML → reports/TIMESTAMP/junit-report.xml
    config.option.xmlpath = os.path.join(run_dir, "junit-report.xml")

    # pytest-html → reports/TIMESTAMP/report.html
    if hasattr(config.option, "htmlpath"):
        config.option.htmlpath = os.path.join(run_dir, "report.html")

    # Store run dir for other fixtures
    config._run_dir = run_dir
    config._allure_dir = allure_dir

    logger.info(f"Run directory: {run_dir}")


# ── Load config & test data ──

@pytest.fixture(scope="session")
def config(request) -> dict:
    """Load config.yaml once per session."""
    cfg = dict(_raw_config)

    # Use the run directory from pytest_configure
    run_dir = getattr(request.config, "_run_dir",
                      os.path.join(ROOT_DIR, "reports", "default"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshots_dir = os.path.join(
        ROOT_DIR, cfg.get("screenshots_dir", "screenshots"), timestamp
    )
    os.makedirs(screenshots_dir, exist_ok=True)

    cfg["_run_reports_dir"] = run_dir
    cfg["_run_screenshots_dir"] = screenshots_dir

    logger.info(f"Report directory: {run_dir}")
    logger.info(f"Screenshots directory: {screenshots_dir}")
    return cfg


@pytest.fixture(scope="session")
def test_data() -> dict:
    """Load test_data.json once per session."""
    data_path = os.path.join(ROOT_DIR, "config", "test_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Browser & Page fixtures ──
# Parametrized by browser — each test runs on every configured browser.
# This implements the browser matrix requirement: Chrome/Firefox/Edge.
# With pytest-xdist (-n N), these run in parallel with session isolation.

@pytest_asyncio.fixture(scope="function", params=_BROWSERS, ids=lambda b: b["name"])
async def page(request, config):
    """
    Create a browser + isolated page for each test.

    BROWSER MATRIX: Parametrized by browser from config.yaml.
    SESSION ISOLATION: Each test gets its own Playwright → Browser → Context → Page.
    No state is shared between tests running in parallel.
    """
    browser_def = request.param
    browser_name = browser_def.get("name", "chromium")
    channel = browser_def.get("channel", None)

    factory = BrowserFactory(config)
    browser = await factory.create_browser(browser_name, channel)
    context = await browser.new_context()
    p = await context.new_page()

    # Set default timeouts from config
    default_timeout = config.get("timeouts", {}).get("default", 30000)
    p.set_default_timeout(default_timeout)

    nav_timeout = config.get("timeouts", {}).get("navigation", 60000)
    p.set_default_navigation_timeout(nav_timeout)

    # Tag Allure report with browser name
    allure.dynamic.tag(f"browser:{browser_name}")
    allure.dynamic.parameter("browser", browser_name)

    yield p

    # Cleanup — each test cleans its own session
    await p.close()
    await context.close()
    await browser.close()
    await factory.cleanup()


# ── Allure hooks ──

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach failure info to Allure on test failure."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        allure.attach(
            f"Test failed: {item.name}\nPhase: {call.when}",
            name="failure_info",
            attachment_type=allure.attachment_type.TEXT,
        )


def pytest_sessionfinish(session, exitstatus):
    """Print report locations after test run."""
    run_dir = getattr(session.config, "_run_dir", None)
    if run_dir:
        print(f"\n{'=' * 60}")
        print(f"  REPORTS GENERATED:")
        print(f"  HTML Report:  {os.path.join(run_dir, 'report.html')}")
        print(f"  JUnit XML:    {os.path.join(run_dir, 'junit-report.xml')}")
        print(f"  Allure Data:  {os.path.join(run_dir, 'allure-results')}")
        print(f"")
        print(f"  To view Allure report:")
        print(f"    allure serve \"{os.path.join(run_dir, 'allure-results')}\"")
        print(f"{'=' * 60}")
