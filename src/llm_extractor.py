"""
LLM-based structured data extraction using Groq (Llama 3.3 70B).

Takes cleaned page text from university websites and extracts structured
data matching the UniversityData Pydantic schema using JSON mode output.
"""

import json
import logging
import sys
import os

from openai import OpenAI

# Ensure we can import from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import GROQ_API_KEY, GROQ_BASE_URL, MODEL_NAME, EXTRACTION_SCHEMA, SYSTEM_PROMPT
from schema import (
    UniversityData, Overview, Location, Contact,
    TuitionItem, AdmissionDeadline, PageMetadata
)

logger = logging.getLogger(__name__)

# Initialize the Groq client
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url=GROQ_BASE_URL,
)

def extract_university_data(pages: list, domain_url: str = "") -> dict:
    """
    Extract structured university data from cleaned page content using Groq LLM.

    Sends all page content in a single LLM call with the full schema,
    and uses JSON mode for structured output.

    Args:
        pages: List of dicts with keys: 'url', 'category', 'cleaned_text'
        domain_url: The original domain URL (for logging)

    Returns:
        Dict matching the UniversityData schema structure.
    """
    # Build the user prompt with all page content
    page_sections = []
    for page in pages:
        section = f"[URL: {page['url']} | Category: {page['category']}]\n{page['cleaned_text']}"
        page_sections.append(section)

    all_content = "\n\n---PAGE BREAK---\n\n".join(page_sections)
    with open("debug_llm_input.txt", "w", encoding="utf-8") as f:
        f.write(all_content)  
    user_prompt = f"""Extract university information from the following web page content into this exact JSON schema:

    {EXTRACTION_SCHEMA}

    PAGE CONTENT:
    {all_content}

    Return ONLY the JSON object. No explanation, no markdown code blocks."""

    logger.info(f"Sending {len(pages)} pages to LLM for extraction ({len(all_content)} chars)")

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for deterministic extraction
        )

        raw_response = completion.choices[0].message.content
        logger.info(f"LLM response received ({len(raw_response)} chars)")

        # Parse the JSON response
        data = json.loads(raw_response)
        logger.info(f"Successfully parsed LLM JSON response")

        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Raw response: {raw_response[:500]}")
        return {}

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return {}


def build_university_data(extracted: dict, page_metadata: list) -> UniversityData:
    """
    Convert the raw extracted dict into a validated UniversityData Pydantic model.

    Handles missing fields gracefully — sets them to None instead of crashing.

    Args:
        extracted: Dict from extract_university_data()
        page_metadata: List of PageMetadata objects for pages used

    Returns:
        Validated UniversityData instance.
    """
    try:
        # Build Overview
        overview_data = extracted.get("overview", {}) or {}
        location_data = overview_data.get("location", {}) or {}
        contact_data = overview_data.get("contact", {}) or {}

        location = Location(
            city=location_data.get("city"),
            state=location_data.get("state"),
            country=location_data.get("country"),
            postal_code=location_data.get("postal_code"),
        )

        contact = Contact(
            phone=contact_data.get("phone"),
            email=contact_data.get("email"),
        )

        overview = Overview(
            university_name=overview_data.get("university_name"),
            location=location,
            contact=contact,
        )

        # Build Tuition Breakdown
        tuition_items = []
        for item in extracted.get("tuition_breakdown", []) or []:
            try:
                tuition_items.append(TuitionItem(
                    fee_type=item.get("fee_type"),
                    cost=int(item["cost"]) if item.get("cost") is not None else None,
                    currency=item.get("currency"),
                ))
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid tuition item: {item} — {e}")

        # Build Admission Deadlines
        deadlines = []
        for item in extracted.get("admission_deadlines", []) or []:
            try:
                deadlines.append(AdmissionDeadline(
                    deadline_type=item.get("deadline_type"),
                    deadline_date=item.get("deadline_date"),
                    notes=item.get("notes"),
                ))
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid deadline: {item} — {e}")

        university_data = UniversityData(
            overview=overview,
            tuition_breakdown=tuition_items,
            admission_deadlines=deadlines,
            page_metadata=page_metadata,
        )

        logger.info(
            f"Built UniversityData: "
            f"name={overview.university_name}, "
            f"{len(tuition_items)} tuition items, "
            f"{len(deadlines)} deadlines, "
            f"{len(page_metadata)} pages"
        )

        return university_data

    except Exception as e:
        logger.error(f"Failed to build UniversityData: {e}")
        # Return a minimal valid object
        return UniversityData(page_metadata=page_metadata)
