"""
HTTP fetching layer with retry logic, timeouts, and structured logging.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import REQUEST_TIMEOUT, MAX_RETRIES, USER_AGENT

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of an HTTP fetch attempt."""
    url: str
    status_code: Optional[int] = None
    html: Optional[str] = None
    error: Optional[str] = None
    response_time: float = 0.0
    success: bool = False


def fetch_page(url: str) -> FetchResult:
    """
    Fetch a web page with retry logic and exponential backoff.

    - Custom User-Agent header (some university sites block default python-requests)
    - Configurable timeout
    - 3 retry attempts with exponential backoff (1s -> 2s -> 4s)
    - Skips non-200 responses, auth-required pages (401/403), and non-HTML content
    - Structured logging for every request

    Args:
        url: The URL to fetch.

    Returns:
        FetchResult with status_code, html content, and metadata.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        start_time = time.time()

        try:
            logger.info(f"[Attempt {attempt}/{MAX_RETRIES}] Fetching: {url}")
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            elapsed = time.time() - start_time

            # Auth-required pages — skip immediately, no retry
            if response.status_code in (401, 403):
                logger.warning(f"Auth-required ({response.status_code}), skipping: {url}")
                return FetchResult(
                    url=url,
                    status_code=response.status_code,
                    error=f"Authentication required (HTTP {response.status_code})",
                    response_time=elapsed,
                )

            # Non-HTML content — skip immediately, no retry
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                logger.warning(f"Non-HTML content ({content_type}), skipping: {url}")
                return FetchResult(
                    url=url,
                    status_code=response.status_code,
                    error=f"Non-HTML content type: {content_type}",
                    response_time=elapsed,
                )

            # Non-200 responses — retry on server errors (5xx), skip on client errors (4xx)
            if response.status_code != 200:
                if response.status_code >= 500 and attempt < MAX_RETRIES:
                    backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    logger.warning(
                        f"Server error ({response.status_code}), retrying in {backoff}s: {url}"
                    )
                    last_error = f"HTTP {response.status_code}"
                    time.sleep(backoff)
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code}, skipping: {url}")
                    return FetchResult(
                        url=url,
                        status_code=response.status_code,
                        error=f"HTTP {response.status_code}",
                        response_time=elapsed,
                    )

            # Success
            logger.info(f"Fetched successfully ({elapsed:.2f}s): {url}")
            return FetchResult(
                url=url,
                status_code=200,
                html=response.text,
                response_time=elapsed,
                success=True,
            )

        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            last_error = "Request timed out"
            logger.warning(f"Timeout after {elapsed:.2f}s (attempt {attempt}/{MAX_RETRIES}): {url}")

        except requests.exceptions.ConnectionError as e:
            elapsed = time.time() - start_time
            last_error = f"Connection error: {e}"
            logger.warning(f"Connection error (attempt {attempt}/{MAX_RETRIES}): {url} — {e}")

        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            last_error = f"Request failed: {e}"
            logger.error(f"Request exception (attempt {attempt}/{MAX_RETRIES}): {url} — {e}")

        # Exponential backoff before next retry
        if attempt < MAX_RETRIES:
            backoff = 2 ** (attempt - 1)
            logger.info(f"Retrying in {backoff}s...")
            time.sleep(backoff)

    # All retries exhausted
    logger.error(f"All {MAX_RETRIES} attempts failed for: {url}")
    return FetchResult(
        url=url,
        error=last_error or "Unknown error after all retries",
    )
