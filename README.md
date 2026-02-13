# eBay Automation Project

E2E automation framework for eBay — search, filter by price, add to cart, and verify cart total.

## Test Run Screenshots

Screenshots captured automatically during a full E2E run via Selenoid Docker Grid:

| Step | Screenshot |
|---|---|
| **1. Guest Login** — navigate to eBay homepage | ![Guest Login](docs/screenshots/01_guest_login_homepage.png) |
| **2. Search** — search for "shoes" | ![Search Results](docs/screenshots/02_search_results.png) |
| **3. Price Filter** — apply max price $220 | ![Price Filter](docs/screenshots/03_price_filter_applied.png) |
| **4. Add to Cart** — item added successfully | ![Add to Cart](docs/screenshots/04_item_added_to_cart.png) |
| **5. Cart Verification** — blocked by captcha (expected from Docker IP) | ![Cart Captcha](docs/screenshots/05_cart_captcha.png) |

> These screenshots are captured automatically by the framework at each test step and attached to the Allure report.

---

## Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.11+** | Language |
| **Playwright** (async) | Browser automation |
| **pytest** + pytest-asyncio | Test framework |
| **Allure Reports** | Rich HTML reports with screenshots & steps |
| **pytest-html** | Standalone HTML report |
| **JUnit XML** | CI-compatible report format |
| **Selenoid** (Docker) | Remote browser execution via Grid |
| **pytest-xdist** | Parallel test execution |

## Architecture

- **POM (Page Object Model)** — each page is a class inheriting from `BasePage`
- **ResilientLocator** — 2+ alternative locators per element with automatic fallback
- **Data-Driven** — test data from `config/test_data.json`, config from `config/config.yaml`
- **SRP** — Page Objects return data only; assertions live in the test layer

## Project Structure

```
Ebay_Automation_Project/
├── config/
│   ├── config.yaml              # URLs, timeouts, grid settings, browser list
│   └── test_data.json           # Test cases (queries, prices, limits, credentials)
├── core/
│   ├── base_page.py             # BasePage — shared operations (click, fill, navigate)
│   ├── browser_factory.py       # Creates browsers: local or remote via Selenoid CDP
│   └── locator_utility.py       # ResilientLocator — smart locator with fallback
├── pages/
│   ├── login_page.py            # LoginPage — stub/guest mode or real login
│   ├── search_results_page.py   # SearchResultsPage — search + price filter + pagination
│   ├── item_details_page.py     # ItemDetailsPage — variant selection + Add to Cart
│   └── cart_page.py             # CartPage — open cart + get total (data only)
├── tests/
│   ├── conftest.py              # Fixtures: browser matrix, page, config, allure hooks
│   └── test_e2e_flow.py         # E2E test — data-driven + helper functions
├── utils/
│   ├── logger.py                # Logging (console + file)
│   ├── retry.py                 # Retry with exponential backoff decorator
│   └── screenshot.py            # Screenshot capture + Allure attachment
├── selenoid-config/
│   └── browsers.json            # Selenoid browser images configuration
├── docker-compose.yml           # Selenoid + Selenoid UI + Test Runner containers
├── Dockerfile                   # Test runner container image
├── .dockerignore                # Excludes venv, cache, reports from Docker build
├── pytest.ini                   # pytest settings (asyncio mode, markers, addopts)
└── requirements.txt             # Python dependencies
```

---

## Prerequisites

- **Python 3.11** or higher
- **Docker Desktop** (for Selenoid Grid execution)
- **Allure CLI** (for viewing Allure reports) — [install guide](https://docs.qameta.io/allure/#_installing_a_commandline)

---

## Setup & Installation

### 1. Clone and create virtual environment

```bash
git clone <repository-url>
cd Ebay_Automation_Project

# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
playwright install
```

### 4. Verify installation

```bash
# Check pytest discovers the tests
pytest --collect-only
```

---

## Running Tests Locally (No Docker)

Make sure `config/config.yaml` has grid **disabled**:

```yaml
grid:
  enabled: false
```

Then run:

```bash
# Run all tests
pytest tests/ -v

# Run with parallel workers
pytest tests/ -n 3 -v
```

---

## Running Tests via Selenoid Grid (Docker)

### Step 1: Pull browser Docker images

Selenoid runs each browser inside a Docker container. You must pull the required images **before** starting the grid:

```bash
docker pull selenoid/vnc:chrome_128.0
docker pull selenoid/vnc:firefox_125.0
```

### Step 2: Start Selenoid containers

```bash
docker-compose up -d
```

This starts two services:

| Service | Port | Description |
|---|---|---|
| **Selenoid** | `4444` | Browser grid manager — receives session requests |
| **Selenoid UI** | `8090` | Live dashboard with VNC viewer |

### Step 3: Verify Selenoid is running

```bash
# Check containers are up
docker-compose ps

# Check Selenoid status API
curl http://localhost:4444/wd/hub/status
```

Open the Selenoid UI dashboard in your browser: **http://localhost:8090**

### Step 4: Enable Grid in config

Edit `config/config.yaml`:

```yaml
grid:
  enabled: true
  url: "http://localhost:4444/wd/hub"
```

### Step 5: Run tests through Selenoid

```bash
pytest tests/ -v
```

While tests are running, open **http://localhost:8090** to watch live browser sessions. Click on a running session to see the VNC stream.

### Step 6: Stop Selenoid when done

```bash
docker-compose down
```

---

## Running Tests in a Docker Container (Full Stack)

Instead of running pytest on your host machine, you can run the test runner itself inside a Docker container alongside Selenoid. This gives you a fully reproducible, single-command setup.

### One command to run everything

```bash
docker-compose --profile tests up
```

This starts **three** services:

| Service | Port | Description |
|---|---|---|
| **Selenoid** | `4444` | Browser grid manager |
| **Selenoid UI** | `8090` | Live dashboard with VNC viewer |
| **Tests** | — | pytest running in a container |

The test runner container automatically connects to Selenoid via Docker networking (`GRID_URL` environment variable) — no config changes needed.

### Build the test runner image

```bash
docker-compose build tests
```

### View results

Reports, screenshots, and logs are mounted to your host via Docker volumes:

```
reports/        ← Allure results, HTML report, JUnit XML
screenshots/    ← Failure & step screenshots
logs/           ← Test run logs
```

### Stop everything

```bash
docker-compose --profile tests down
```

> **Note:** Running `docker-compose up -d` (without `--profile tests`) starts only Selenoid + UI, so local development with `pytest` on the host still works as before.

---

## Viewing Reports

Each test run creates a unique timestamped directory under `reports/`:

```
reports/
└── 20260212_143022/
    ├── allure-results/    # Allure raw data (JSON files)
    ├── report.html        # Standalone HTML report
    └── junit-report.xml   # JUnit XML for CI tools
```

The exact path is printed at the end of every test run.

### Allure Report (interactive)

```bash
allure serve reports/<TIMESTAMP>/allure-results
```

For example:

```bash
allure serve reports/20260212_143022/allure-results
```

This opens a rich interactive report with test steps, screenshots, locator details, and failure info.

### HTML Report (standalone)

Open `reports/<TIMESTAMP>/report.html` directly in any browser — no server needed.

### JUnit XML

Import `reports/<TIMESTAMP>/junit-report.xml` into CI tools (Jenkins, GitLab CI, Azure DevOps, etc.).

---

## Configuration Reference

### config/config.yaml

| Setting | Description | Default |
|---|---|---|
| `base_url` | eBay base URL | `https://www.ebay.com` |
| `timeouts.default` | Default element timeout (ms) | `30000` |
| `timeouts.navigation` | Page navigation timeout (ms) | `60000` |
| `timeouts.element` | Element wait timeout (ms) | `10000` |
| `grid.enabled` | Enable Selenoid Grid | `false` |
| `grid.url` | Selenoid Grid URL | `http://localhost:4444/wd/hub` |
| **Env: `GRID_URL`** | Overrides `grid.url` and enables grid (used by Docker) | — |
| `browsers` | Browser matrix list | chromium, firefox, webkit |
| `retry.max_attempts` | Max retry attempts | `3` |
| `retry.backoff_base` | Base delay for backoff (seconds) | `1.0` |
| `retry.backoff_factor` | Exponential backoff multiplier | `2.0` |
| `headless` | Run browsers in headless mode | `false` |

### config/test_data.json

Each test case:

```json
{
  "query": "shoes",
  "max_price": 220,
  "limit": 5,
  "credentials": {
    "username": "test_user",
    "password": "test_pass"
  }
}
```

- `query` — search term on eBay
- `max_price` — maximum price filter
- `limit` — max number of items to collect and add to cart
- `credentials` — use `"test_user"` for guest/stub mode; real credentials for actual login

---

## Key Features

### 4 Main Functions

| # | Function | Location | Description |
|---|---|---|---|
| 1 | `login()` | `pages/login_page.py` | Stub/guest mode or real login with captcha handling |
| 2 | `search_items_by_name_under_price()` | `pages/search_results_page.py` | Search + price filter + pagination |
| 3 | `add_items_to_cart()` | `tests/test_e2e_flow.py` | Navigate to items, select variants, add to cart |
| 4 | `assert_cart_total_not_exceeds()` | `tests/test_e2e_flow.py` | Open cart, read total, assert within budget |

### Smart Locators (ResilientLocator)

Each UI element has 2+ alternative locator strategies (CSS + XPath). If the primary locator fails, the next is tried automatically:

- Every attempt is logged with strategy, value, and attempt number
- Every attempt is attached to the Allure report as a step
- A screenshot is captured on final failure before raising

### Browser Matrix

Tests are parametrized across browsers defined in `config.yaml`:
- **Local mode** — chromium, firefox, webkit
- **Grid mode** — chrome only (Selenoid supports Chrome via CDP)

### Session Isolation

Each test gets its own `Playwright -> Browser -> BrowserContext -> Page`. No state is shared between tests, even when running in parallel with `pytest-xdist`.

### Retry with Exponential Backoff

- **Navigation**: automatic retry with backoff on `BasePage.navigate()`
- **Add to Cart**: `@retry_with_backoff` decorator on the click action
- **Configurable**: `max_attempts`, `backoff_base`, `backoff_factor` in config.yaml

---

## Docker Architecture

### Local dev mode (`docker-compose up -d`)

```
┌─────────────────────────────────────────────────┐
│  Host Machine                                   │
│                                                 │
│  ┌──────────────┐    ┌───────────────────────┐  │
│  │  pytest       │    │  Selenoid (port 4444) │  │
│  │  (your tests) │───>│  Grid manager         │  │
│  └──────────────┘    └──────────┬────────────┘  │
│                                 │                │
│                     ┌───────────┴──────────┐     │
│                     │  Browser Containers  │     │
│                     │  ┌────────────────┐  │     │
│                     │  │ Chrome 128.0   │  │     │
│                     │  │ (selenoid/vnc) │  │     │
│                     │  └────────────────┘  │     │
│                     └──────────────────────┘     │
│                                                 │
│  ┌─────────────────────────────┐                │
│  │  Selenoid UI (port 8090)    │                │
│  │  Live dashboard + VNC view  │                │
│  └─────────────────────────────┘                │
└─────────────────────────────────────────────────┘
```

### Full Docker mode (`docker-compose --profile tests up`)

```
┌──────────────────────────────────────────────────────┐
│  Docker Network (grid)                               │
│                                                      │
│  ┌──────────────────┐    ┌───────────────────────┐   │
│  │  Test Runner      │    │  Selenoid (port 4444) │   │
│  │  (pytest in       │───>│  Grid manager         │   │
│  │   container)      │    └──────────┬────────────┘   │
│  │                   │               │                │
│  │  GRID_URL=        │   ┌───────────┴──────────┐     │
│  │  selenoid:4444    │   │  Browser Containers  │     │
│  └──────────────────┘   │  ┌────────────────┐  │     │
│          │               │  │ Chrome 128.0   │  │     │
│          ▼               │  │ (selenoid/vnc) │  │     │
│  ┌──────────────────┐   │  └────────────────┘  │     │
│  │  Volumes (host)   │   └──────────────────────┘     │
│  │  ./reports/       │                                │
│  │  ./screenshots/   │   ┌─────────────────────────┐  │
│  │  ./logs/          │   │  Selenoid UI (port 8090) │  │
│  └──────────────────┘   └─────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

**Connection flow:**

1. pytest calls `BrowserFactory.create_browser()`
2. BrowserFactory sends `POST /wd/hub/session` to Selenoid
3. Selenoid creates a browser container and returns `se:cdp` WebSocket URL
4. Playwright connects via `connect_over_cdp()`
5. Tests run through the CDP connection
6. On cleanup: `DELETE /session` — Selenoid destroys the container

> In full Docker mode, the test runner reaches Selenoid via Docker DNS (`selenoid:4444`) instead of `localhost:4444`. This is handled automatically by the `GRID_URL` environment variable.
