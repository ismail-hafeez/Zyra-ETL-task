"""
Tests for the Pydantic schema models.

Validates that the schema accepts valid data, rejects invalid data,
and handles edge cases gracefully.
"""

import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from schema import (
    Location, Contact, Overview, TuitionItem,
    DeadlineType, AdmissionDeadline, PageMetadata, UniversityData
)
from pydantic import ValidationError


# ── Location ─────────────────────────────────────────────────────

class TestLocation:
    def test_valid_full_location(self):
        loc = Location(city="Lewisburg", state="PA", country="USA", postal_code="17837")
        assert loc.city == "Lewisburg"
        assert loc.state == "PA"
        assert loc.country == "USA"
        assert loc.postal_code == "17837"

    def test_all_none_location(self):
        """All fields are optional — all-None should be valid."""
        loc = Location()
        assert loc.city is None
        assert loc.state is None

    def test_partial_location(self):
        loc = Location(city="Washington", state="DC")
        assert loc.city == "Washington"
        assert loc.country is None


# ── Contact ──────────────────────────────────────────────────────

class TestContact:
    def test_valid_contact(self):
        contact = Contact(phone="570-577-3000", email="admissions@bucknell.edu")
        assert contact.phone == "570-577-3000"
        assert contact.email == "admissions@bucknell.edu"

    def test_none_contact(self):
        contact = Contact()
        assert contact.phone is None
        assert contact.email is None

    def test_invalid_email_rejected(self):
        """EmailStr should reject garbage strings."""
        with pytest.raises(ValidationError):
            Contact(email="not-an-email")

    def test_valid_email_formats(self):
        contact = Contact(email="test@university.edu")
        assert contact.email == "test@university.edu"


# ── TuitionItem ──────────────────────────────────────────────────

class TestTuitionItem:
    def test_valid_tuition_item(self):
        item = TuitionItem(fee_type="Tuition", cost=72600, currency="USD")
        assert item.fee_type == "Tuition"
        assert item.cost == 72600
        assert item.currency == "USD"

    def test_cost_must_be_int(self):
        """Cost field is Optional[int] — string should fail."""
        with pytest.raises(ValidationError):
            TuitionItem(cost="not_a_number")

    def test_none_cost_allowed(self):
        item = TuitionItem(fee_type="Tuition", cost=None)
        assert item.cost is None

    def test_zero_cost_allowed(self):
        """Some universities offer free tuition."""
        item = TuitionItem(fee_type="Tuition", cost=0, currency="USD")
        assert item.cost == 0


# ── DeadlineType Enum ────────────────────────────────────────────

class TestDeadlineType:
    def test_valid_enum_values(self):
        assert DeadlineType.EARLY_DECISION == "Early Decision"
        assert DeadlineType.REGULAR_DECISION == "Regular Decision"
        assert DeadlineType.TRANSFER_ADMISSION == "Transfer Admission"

    def test_enum_from_value(self):
        dt = DeadlineType("Early Decision")
        assert dt == DeadlineType.EARLY_DECISION

    def test_invalid_enum_value(self):
        with pytest.raises(ValueError):
            DeadlineType("Rolling Admission")


# ── AdmissionDeadline ────────────────────────────────────────────

class TestAdmissionDeadline:
    def test_valid_deadline(self):
        dl = AdmissionDeadline(
            deadline_type=DeadlineType.EARLY_DECISION,
            deadline_date="2026-11-15",
            notes="Application due"
        )
        assert dl.deadline_type == DeadlineType.EARLY_DECISION
        assert dl.deadline_date == "2026-11-15"

    def test_none_deadline_type(self):
        """deadline_type can be null for non-standard deadlines."""
        dl = AdmissionDeadline(deadline_type=None, deadline_date="June 30", notes="Fiscal year end")
        assert dl.deadline_type is None

    def test_deadline_with_string_enum_value(self):
        dl = AdmissionDeadline(deadline_type="Regular Decision")
        assert dl.deadline_type == DeadlineType.REGULAR_DECISION


# ── UniversityData (top-level model) ─────────────────────────────

class TestUniversityData:
    def test_empty_university_data(self):
        """Default values should produce a valid object."""
        data = UniversityData()
        assert data.overview is None
        assert data.tuition_breakdown == []
        assert data.admission_deadlines == []
        assert data.page_metadata == []

    def test_full_university_data(self):
        data = UniversityData(
            overview=Overview(
                university_name="Test University",
                location=Location(city="Test City", state="TS", country="USA", postal_code="12345"),
                contact=Contact(phone="555-1234", email="info@test.edu"),
            ),
            tuition_breakdown=[
                TuitionItem(fee_type="Tuition", cost=50000, currency="USD"),
            ],
            admission_deadlines=[
                AdmissionDeadline(deadline_type="Early Decision", deadline_date="2026-11-15"),
            ],
            page_metadata=[
                PageMetadata(url="https://test.edu", page_title="Test", scraped_at="2026-01-01T00:00:00Z", status_code="200"),
            ],
        )
        assert data.overview.university_name == "Test University"
        assert len(data.tuition_breakdown) == 1
        assert len(data.admission_deadlines) == 1
        assert len(data.page_metadata) == 1

    def test_json_serialization(self):
        """model_dump_json should produce valid JSON."""
        data = UniversityData(
            overview=Overview(university_name="Test U"),
            tuition_breakdown=[TuitionItem(fee_type="Tuition", cost=10000, currency="USD")],
        )
        json_str = data.model_dump_json(indent=2)
        assert '"university_name": "Test U"' in json_str
        assert '"cost": 10000' in json_str

    def test_page_metadata_fields(self):
        pm = PageMetadata(
            url="https://test.edu",
            page_title="Test Page",
            scraped_at="2026-06-01T12:00:00Z",
            status_code="200"
        )
        assert pm.url == "https://test.edu"
        assert pm.status_code == "200"
