"""
Link discovery and page classification for university websites.

BFS crawl (max depth 2): Homepage -> hub pages -> detail pages.
Uses keyword matching on URL paths and anchor text to find
Admissions and Tuition/Cost pages without hardcoding URLs.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import CRAWL_MAX_DEPTH, ADMISSION_KEYWORDS, TUITION_KEYWORDS
from crawlers.fetcher import fetch_page

logger = logging.getLogger(__name__)


# File extensions and prefixes to skip when extracting links
SKIP_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.jpg', '.png', '.gif', '.mp4', '.mp3'}
SKIP_PREFIXES = {'mailto:', 'tel:', 'javascript:', 'data:', 'ftp:'}


@dataclass
class CategorizedPage:
    """A discovered page with its category and relevance score."""
    url: str
    category: str  # "ADMISSIONS", "TUITION", or "GENERAL"
    score: float
    anchor_text: str = ""
    depth: int = 0

def _extract_links(html: str, base_url: str) -> List[dict]:
    """
    Parse all <a> tags from HTML and return normalized, filtered links.

    - Resolves relative URLs to absolute
    - Filters out fragments, mailto, tel, file downloads, external domains

    Args:
        html: Raw HTML content.
        base_url: The base URL for resolving relative links.

    Returns:
        List of dicts with 'url' and 'anchor_text' keys.
    """
    soup = BeautifulSoup(html, 'html.parser')
    base_domain = urlparse(base_url).netloc.lower()
    links = []
    seen_urls = set()

    for tag in soup.find_all('a', href=True):
        href = tag['href'].strip()

        # Skip empty, fragments-only, and special prefixes
        if not href or href.startswith('#'):
            continue
        if any(href.lower().startswith(prefix) for prefix in SKIP_PREFIXES):
            continue

        # Resolve to absolute URL
        absolute_url = urljoin(base_url, href)

        # Remove fragments and trailing whitespace
        parsed = urlparse(absolute_url)
        clean_url = parsed._replace(fragment='').geturl()

        # Skip file downloads
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
            continue

        # Same-domain filter
        link_domain = parsed.netloc.lower()
        if link_domain and link_domain != base_domain:
            # Allow subdomains (e.g., admissions.bucknell.edu for bucknell.edu)
            root_domain = '.'.join(base_domain.split('.')[-2:])
            link_root = '.'.join(link_domain.split('.')[-2:])
            if link_root != root_domain:
                continue

        # Deduplicate
        if clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        anchor_text = tag.get_text(strip=True).lower()
        links.append({
            'url': clean_url,
            'anchor_text': anchor_text,
        })

    logger.info(f"Extracted {len(links)} unique same-domain links from {base_url}")
    return links


def _score_relevance(url: str, anchor_text: str) -> tuple:
    """
    Score a link's relevance for admissions or tuition content.

    Checks keyword matches against URL path segments and anchor text.

    Returns:
        (score, category) — score is a float, category is "ADMISSIONS", "TUITION", or "GENERAL".
    """
    path = urlparse(url).path.lower()
    anchor = anchor_text.lower()

    admission_score = 0.0
    tuition_score = 0.0

    for keyword in ADMISSION_KEYWORDS:
        if keyword in path:
            admission_score += 2.0  # URL match = high signal
        if keyword in anchor:
            admission_score += 1.0  # Anchor text match = medium signal

    for keyword in TUITION_KEYWORDS:
        if keyword in path:
            tuition_score += 2.0
        if keyword in anchor:
            tuition_score += 1.0

    # Classify by the higher score
    if tuition_score > admission_score and tuition_score > 0:
        return (tuition_score, "TUITION")
    elif admission_score > 0:
        return (admission_score, "ADMISSIONS")
    else:
        return (0.0, "GENERAL")


def discover_relevant_pages(domain_url: str) -> List[CategorizedPage]:
    """
    Discover admissions and tuition pages via BFS crawl (max depth 2).

    Algorithm:
        1. Depth 0: Fetch homepage, extract all links, score for relevance.
        2. Depth 1: Fetch top relevant hub pages, extract their links, score again.
        3. Collect all pages with score > 0, deduplicated and sorted by score.

    Args:
        domain_url: The university's base domain URL (e.g., "https://www.bucknell.edu").

    Returns:
        List of CategorizedPage objects sorted by relevance score (highest first).
    """
    logger.info(f"Starting page discovery for: {domain_url}")

    discovered = {}  # url -> CategorizedPage
    visited = set()  # URLs already fetched
    to_crawl = [(domain_url, 0)]  # (url, depth) queue

    while to_crawl:
        current_url, depth = to_crawl.pop(0)

        if depth > CRAWL_MAX_DEPTH:
            continue
        if current_url in visited:
            continue

        visited.add(current_url)
        logger.info(f"[Depth {depth}] Crawling: {current_url}")

        # Fetch the page
        result = fetch_page(current_url)
        if not result.success or not result.html:
            logger.warning(f"Failed to fetch {current_url}: {result.error}")
            continue

        # Extract links from this page
        links = _extract_links(result.html, current_url)

        for link in links:
            link_url = link['url']
            anchor_text = link['anchor_text']

            # Score this link
            score, category = _score_relevance(link_url, anchor_text)

            if score > 0:
                # Track the best score for each URL
                if link_url not in discovered or score > discovered[link_url].score:
                    discovered[link_url] = CategorizedPage(
                        url=link_url,
                        category=category,
                        score=score,
                        anchor_text=anchor_text,
                        depth=depth + 1,
                    )

                # Queue relevant pages for deeper crawling if within depth limit
                if link_url not in visited and (depth + 1) < CRAWL_MAX_DEPTH:
                    to_crawl.append((link_url, depth + 1))

    # Sort by score descending
    results = sorted(discovered.values(), key=lambda p: p.score, reverse=True)

    # Log summary
    admissions = [p for p in results if p.category == "ADMISSIONS"]
    tuition = [p for p in results if p.category == "TUITION"]
    logger.info(
        f"Discovery complete for {domain_url}: "
        f"{len(results)} relevant pages found "
        f"({len(admissions)} admissions, {len(tuition)} tuition)"
    )
    for page in results:
        logger.info(f"  [{page.category}] (score={page.score:.1f}, depth={page.depth}) {page.url}")

    return results
