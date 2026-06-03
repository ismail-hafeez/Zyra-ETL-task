"""
Tests for the crawler modules (fetcher and discovery).

Uses mocked HTTP responses to test link extraction, relevance scoring,
URL resolution, retry logic, and page discovery without making real requests.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from crawlers.fetcher import fetch_page, FetchResult
from crawlers.discovery import _extract_links, _score_relevance, discover_relevant_pages


# ── _extract_links ───────────────────────────────────────────────

class TestExtractLinks:
    def test_extracts_absolute_urls(self):
        html = '<html><body><a href="https://www.test.edu/admissions">Apply</a></body></html>'
        links = _extract_links(html, "https://www.test.edu")
        assert len(links) == 1
        assert links[0]['url'] == "https://www.test.edu/admissions"

    def test_resolves_relative_urls(self):
        html = '<html><body><a href="/admissions/deadlines">Deadlines</a></body></html>'
        links = _extract_links(html, "https://www.test.edu")
        assert links[0]['url'] == "https://www.test.edu/admissions/deadlines"

    def test_filters_external_domains(self):
        html = '''<html><body>
            <a href="https://www.test.edu/local">Local</a>
            <a href="https://www.google.com/search">External</a>
        </body></html>'''
        links = _extract_links(html, "https://www.test.edu")
        urls = [l['url'] for l in links]
        assert "https://www.test.edu/local" in urls
        assert "https://www.google.com/search" not in urls

    def test_filters_mailto_and_tel(self):
        html = '''<html><body>
            <a href="mailto:info@test.edu">Email</a>
            <a href="tel:555-1234">Call</a>
            <a href="/real-page">Real</a>
        </body></html>'''
        links = _extract_links(html, "https://www.test.edu")
        assert len(links) == 1
        assert links[0]['url'] == "https://www.test.edu/real-page"

    def test_filters_pdf_downloads(self):
        html = '''<html><body>
            <a href="/docs/brochure.pdf">Download</a>
            <a href="/admissions">Apply</a>
        </body></html>'''
        links = _extract_links(html, "https://www.test.edu")
        urls = [l['url'] for l in links]
        assert not any('.pdf' in u for u in urls)
        assert "https://www.test.edu/admissions" in urls

    def test_deduplicates_links(self):
        html = '''<html><body>
            <a href="/admissions">Apply</a>
            <a href="/admissions">Apply Again</a>
        </body></html>'''
        links = _extract_links(html, "https://www.test.edu")
        assert len(links) == 1

    def test_strips_fragments(self):
        html = '<html><body><a href="/page#section">Link</a></body></html>'
        links = _extract_links(html, "https://www.test.edu")
        assert '#' not in links[0]['url']

    def test_captures_anchor_text(self):
        html = '<html><body><a href="/page">  Tuition & Fees  </a></body></html>'
        links = _extract_links(html, "https://www.test.edu")
        assert links[0]['anchor_text'] == "tuition & fees"


# ── _score_relevance ────────────────────────────────────────────

class TestScoreRelevance:
    def test_admission_keyword_in_url(self):
        score, category = _score_relevance("https://test.edu/admissions", "")
        assert score > 0
        assert category == "ADMISSIONS"

    def test_tuition_keyword_in_url(self):
        score, category = _score_relevance("https://test.edu/tuition-fees", "")
        assert score > 0
        assert category == "TUITION"

    def test_tuition_beats_admission_when_both_present(self):
        """A URL with more tuition keywords should be categorized as TUITION."""
        score, category = _score_relevance(
            "https://test.edu/admissions-aid/tuition-fees-financial-aid",
            "Tuition & Fees"
        )
        assert category == "TUITION"

    def test_keyword_in_anchor_text(self):
        score, category = _score_relevance("https://test.edu/page", "apply now")
        assert score > 0
        assert category == "ADMISSIONS"

    def test_no_keywords_returns_general(self):
        score, category = _score_relevance("https://test.edu/about-us", "About Us")
        assert score == 0.0
        assert category == "GENERAL"

    def test_url_match_scores_higher_than_anchor(self):
        url_score, _ = _score_relevance("https://test.edu/admissions", "")
        anchor_score, _ = _score_relevance("https://test.edu/page", "admissions")
        assert url_score > anchor_score

    def test_multiple_keywords_increase_score(self):
        single_score, _ = _score_relevance("https://test.edu/tuition", "")
        multi_score, _ = _score_relevance("https://test.edu/tuition-fees-cost", "")
        assert multi_score > single_score


# ── fetch_page (mocked) ─────────────────────────────────────────

class TestFetchPage:
    @patch('crawlers.fetcher.requests.get')
    def test_successful_fetch(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Hello</body></html>"
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_get.return_value = mock_response

        result = fetch_page("https://www.test.edu")
        assert result.success is True
        assert result.status_code == 200
        assert "Hello" in result.html

    @patch('crawlers.fetcher.requests.get')
    def test_auth_required_skipped(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response

        result = fetch_page("https://www.test.edu/protected")
        assert result.success is False
        assert "Authentication required" in result.error

    @patch('crawlers.fetcher.requests.get')
    def test_non_html_skipped(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_get.return_value = mock_response

        result = fetch_page("https://www.test.edu/file.pdf")
        assert result.success is False
        assert "Non-HTML" in result.error

    @patch('crawlers.fetcher.requests.get')
    def test_timeout_returns_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        result = fetch_page("https://www.test.edu")
        assert result.success is False
        assert result.error is not None
