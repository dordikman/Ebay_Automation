FROM python:3.13-slim

WORKDIR /app

# System dependencies for Playwright (no browser binaries — Selenoid provides them)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Default: run all e2e tests with verbose output
CMD ["pytest", "tests/", "-v", "--alluredir=reports/allure-results"]
