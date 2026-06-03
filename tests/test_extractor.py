"""
Tests for the extractor modules (utils and llm_extractor).

Tests HTML cleaning, table preservation, text truncation,
and LLM response parsing with mocked Groq API calls.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import clean_html, extract_page_title, sanitize_filename
from src.llm_extractor import build_university_data
from schema import PageMetadata


# ── clean_html ───────────────────────────────────────────────────

class TestCleanHtml:
    def test_removes_script_tags(self):
        html = '<html><body><script>var x = 1;</script><p>Content</p></body></html>'
        text = clean_html(html)
        assert "var x" not in text
        assert "Content" in text

    def test_removes_style_tags(self):
        html = '<html><body><style>.red { color: red; }</style><p>Content</p></body></html>'
        text = clean_html(html)
        assert "color: red" not in text
        assert "Content" in text

    def test_removes_nav_footer_header(self):
        html = '''<html><body>
            <nav>Menu items</nav>
            <main><p>Main content</p></main>
            <footer>Footer stuff</footer>
        </body></html>'''
        text = clean_html(html)
        assert "Menu items" not in text
        assert "Footer stuff" not in text
        assert "Main content" in text

    def test_preserves_tables_as_pipe_format(self):
        html = '''<html><body>
            <table>
                <tr><th>Fee Type</th><th>Cost</th></tr>
                <tr><td>Tuition</td><td>$50,000</td></tr>
            </table>
        </body></html>'''
        text = clean_html(html)
        assert "Fee Type" in text
        assert "Tuition" in text
        assert "|" in text  # Pipe-delimited format

    def test_truncates_long_content(self):
        html = '<html><body><p>' + 'A' * 20000 + '</p></body></html>'
        text = clean_html(html)
        assert len(text) <= 6100  # 6000 + "[truncated]" suffix
        assert "truncated" in text

    def test_preserves_headings(self):
        html = '<html><body><h2>Tuition & Fees</h2><p>Details here</p></body></html>'
        text = clean_html(html)
        assert "Tuition & Fees" in text

    def test_empty_html_returns_empty(self):
        text = clean_html('<html><body></body></html>')
        assert text.strip() == "" or len(text) < 10

    def test_prefers_main_tag_content(self):
        html = '''<html><body>
            <div>Sidebar noise</div>
            <main><p>Important content</p></main>
        </body></html>'''
        text = clean_html(html)
        assert "Important content" in text


# ── extract_page_title ───────────────────────────────────────────

class TestExtractPageTitle:
    def test_extracts_title(self):
        html = '<html><head><title>Bucknell University | Admissions</title></head><body></body></html>'
        title = extract_page_title(html)
        assert title == "Bucknell University | Admissions"

    def test_no_title_returns_empty(self):
        html = '<html><head></head><body></body></html>'
        title = extract_page_title(html)
        assert title == ""

    def test_strips_whitespace(self):
        html = '<html><head><title>  Test University  </title></head></html>'
        title = extract_page_title(html)
        assert title == "Test University"


# ── sanitize_filename ────────────────────────────────────────────

class TestSanitizeFilename:
    def test_basic_domain(self):
        assert sanitize_filename("https://www.bucknell.edu") == "bucknell_edu"

    def test_strips_www(self):
        assert sanitize_filename("https://www.udc.edu") == "udc_edu"

    def test_handles_trailing_slash(self):
        result = sanitize_filename("https://www.salisbury.edu/")
        assert result == "salisbury_edu"

    def test_handles_hyphens(self):
        result = sanitize_filename("https://www.my-university.edu")
        assert result == "my_university_edu"


# ── build_university_data ────────────────────────────────────────

class TestBuildUniversityData:
    def test_builds_from_valid_dict(self):
        extracted = {
            "overview": {
                "university_name": "Test University",
                "location": {"city": "Test City", "state": "TS", "country": "USA", "postal_code": "12345"},
                "contact": {"phone": "555-1234", "email": "info@test.edu"},
            },
            "tuition_breakdown": [
                {"fee_type": "Tuition", "cost": 50000, "currency": "USD"},
            ],
            "admission_deadlines": [
                {"deadline_type": "Early Decision", "deadline_date": "2026-11-15", "notes": None},
            ],
        }
        metadata = [PageMetadata(url="https://test.edu", page_title="Test", scraped_at="2026-01-01", status_code="200")]

        result = build_university_data(extracted, metadata)
        assert result.overview.university_name == "Test University"
        assert len(result.tuition_breakdown) == 1
        assert result.tuition_breakdown[0].cost == 50000
        assert len(result.admission_deadlines) == 1
        assert len(result.page_metadata) == 1

    def test_handles_empty_dict(self):
        result = build_university_data({}, [])
        assert result.overview is not None  # Should still create an Overview
        assert result.tuition_breakdown == []
        assert result.admission_deadlines == []

    def test_handles_null_fields_gracefully(self):
        extracted = {
            "overview": {
                "university_name": None,
                "location": None,
                "contact": None,
            },
            "tuition_breakdown": [],
            "admission_deadlines": [],
        }
        result = build_university_data(extracted, [])
        assert result.overview.university_name is None

    def test_skips_invalid_tuition_cost(self):
        """Non-numeric cost should be skipped, not crash the pipeline."""
        extracted = {
            "overview": {"university_name": "Test"},
            "tuition_breakdown": [
                {"fee_type": "Tuition", "cost": "not_a_number", "currency": "USD"},
                {"fee_type": "Housing", "cost": 10000, "currency": "USD"},
            ],
            "admission_deadlines": [],
        }
        result = build_university_data(extracted, [])
        # The invalid one should be skipped, valid one kept
        assert len(result.tuition_breakdown) == 1
        assert result.tuition_breakdown[0].fee_type == "Housing"

    def test_json_output_is_valid(self):
        extracted = {
            "overview": {"university_name": "Test U"},
            "tuition_breakdown": [{"fee_type": "Tuition", "cost": 30000, "currency": "USD"}],
            "admission_deadlines": [],
        }
        result = build_university_data(extracted, [])
        json_str = result.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["overview"]["university_name"] == "Test U"
