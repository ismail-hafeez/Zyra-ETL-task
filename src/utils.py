"""
Helper functions for the ETL process.

- clean_html(): Strips noise from HTML, preserves meaningful content for LLM
- extract_page_title(): Pulls the <title> tag
- get_domain(): Generator that yields university URLs from the domains file
- sanitize_filename(): Converts a domain to a safe filename
"""

import os
import re
import sys
import logging
from typing import Generator

from bs4 import BeautifulSoup

# Ensure we can import from the root config file
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger = logging.getLogger(__name__)

# Absolute path to the domains text file
PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'university_domains.txt'))

# Tags that are noise — remove entirely before extracting text
NOISE_TAGS = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'iframe', 'svg']

# Max characters to send to the LLM (roughly ~4000 tokens)
MAX_TEXT_LENGTH = 6000


def clean_html(html: str) -> str:
    """
    Convert raw HTML to clean, readable text suitable for LLM extraction.

    - Removes noise tags (script, style, nav, footer, header, etc.)
    - Preserves table structures (critical for tuition data)
    - Collapses excessive whitespace
    - Truncates to MAX_TEXT_LENGTH characters

    Args:
        html: Raw HTML string.

    Returns:
        Cleaned plain text string.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Remove noise tags
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Try to find the main content area first
    main_content = soup.find('main') or soup.find('article') or soup.find('div', role='main')

    if main_content:
        text = _extract_with_tables(main_content)
    else:
        # Fallback to body
        body = soup.find('body')
        if body:
            text = _extract_with_tables(body)
        else:
            text = _extract_with_tables(soup)

    # Collapse excessive whitespace while preserving paragraph breaks
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    # Truncate if too long
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "\n... [truncated]"
        logger.info(f"Text truncated to {MAX_TEXT_LENGTH} characters")

    logger.info(f"Cleaned HTML to {len(text)} characters of text")
    return text


def _extract_with_tables(element) -> str:
    """
    Extract text from a BeautifulSoup element, preserving table structures
    as pipe-delimited rows so the LLM can understand tabular data.
    """
    parts = []

    for child in element.children:
        if isinstance(child, str):
            stripped = child.strip()
            if stripped:
                parts.append(stripped)
            continue

        if not hasattr(child, 'name'):
            continue

        if child.name == 'table':
            parts.append(_table_to_text(child))
        elif child.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            heading_text = child.get_text(strip=True)
            if heading_text:
                parts.append(f"\n## {heading_text}\n")
        elif child.name == 'br':
            parts.append('\n')
        elif child.name in ('p', 'div', 'section', 'li'):
            inner = _extract_with_tables(child)
            if inner.strip():
                parts.append(inner + '\n')
        else:
            inner = _extract_with_tables(child)
            if inner.strip():
                parts.append(inner)

    return '\n'.join(parts)


def _table_to_text(table_tag) -> str:
    """
    Convert a <table> to a readable pipe-delimited text format.
    Example output:
        | Fee Type | In-State | Out-of-State |
        | Tuition | $12,000 | $28,000 |
    """
    rows = []
    for tr in table_tag.find_all('tr'):
        cells = []
        for td in tr.find_all(['td', 'th']):
            cells.append(td.get_text(strip=True))
        if cells:
            rows.append('| ' + ' | '.join(cells) + ' |')

    return '\n'.join(rows) if rows else ''


def extract_page_title(html: str) -> str:
    """
    Extract the <title> tag text from HTML.

    Args:
        html: Raw HTML string.

    Returns:
        The page title, or empty string if not found.
    """
    soup = BeautifulSoup(html, 'html.parser')
    title_tag = soup.find('title')
    return title_tag.get_text(strip=True) if title_tag else ""


def get_domain() -> Generator[str, None, None]:
    """
    Generator that yields university domain URLs from the domains file.
    """
    with open(PATH, 'r') as f:
        urls = f.read().splitlines()
    for url in urls:
        url = url.strip()
        if url:  # Skip empty lines
            yield url


def sanitize_filename(domain_url: str) -> str:
    """
    Convert a domain URL to a safe filename.
    e.g., "https://www.bucknell.edu" -> "bucknell_edu"

    Args:
        domain_url: The university domain URL.

    Returns:
        A sanitized filename string (no extension).
    """
    from urllib.parse import urlparse
    parsed = urlparse(domain_url)
    hostname = parsed.netloc or parsed.path
    # Remove www. prefix
    hostname = re.sub(r'^www\.', '', hostname)
    # Replace dots and hyphens with underscores
    filename = re.sub(r'[.\-]', '_', hostname)
    # Remove any remaining unsafe characters
    filename = re.sub(r'[^a-zA-Z0-9_]', '', filename)
    return filename
