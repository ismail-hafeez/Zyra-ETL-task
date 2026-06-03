"""
ETL Pipeline Orchestrator.

Ties together crawling, text cleaning, LLM extraction, and validation
into a single run_pipeline() function per university domain.
"""

import json
import logging
import time
import os
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from schema import UniversityData, PageMetadata
from crawlers.fetcher import fetch_page
from crawlers.discovery import discover_relevant_pages
from src.utils import clean_html, extract_page_title, sanitize_filename
from src.llm_extractor import extract_university_data, build_university_data

logger = logging.getLogger(__name__)

# Output directory for JSON results
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'output'))


@dataclass
class PipelineResult:
    """Summary of a single pipeline run for one university."""
    domain_url: str
    success: bool = False
    university_name: Optional[str] = None
    pages_discovered: int = 0
    pages_fetched: int = 0
    tuition_items: int = 0
    deadlines: int = 0
    fields_populated: int = 0
    fields_total: int = 0
    quality_warnings: List[str] = field(default_factory=list)
    output_file: Optional[str] = None
    elapsed_time: float = 0.0
    error: Optional[str] = None


def run_pipeline(domain_url: str) -> PipelineResult:
    """
    Run the full ETL pipeline for a single university domain.

    Steps:
        1. EXTRACT:  Discover relevant pages via BFS crawl
        2. TRANSFORM: Fetch pages, clean HTML, extract text
        3. LOAD:     Send to LLM for structured extraction, validate with Pydantic
        4. SAVE:     Write validated JSON to data/output/

    Args:
        domain_url: The university's base domain URL.

    Returns:
        PipelineResult with execution summary.
    """
    start_time = time.time()
    result = PipelineResult(domain_url=domain_url)

    logger.info(f"{'='*60}")
    logger.info(f"Starting pipeline for: {domain_url}")
    logger.info(f"{'='*60}")

    # ── Step 1: DISCOVER relevant pages ──────────────────────────
    try:
        logger.info("[Step 1/4] Discovering relevant pages...")
        discovered_pages = discover_relevant_pages(domain_url)
        result.pages_discovered = len(discovered_pages)

        if not discovered_pages:
            result.error = "No relevant pages discovered"
            logger.error(f"No relevant pages found for {domain_url}")
            result.elapsed_time = time.time() - start_time
            return result

        logger.info(f"Discovered {len(discovered_pages)} relevant pages")

    except Exception as e:
        result.error = f"Discovery failed: {e}"
        logger.error(f"Discovery failed for {domain_url}: {e}")
        result.elapsed_time = time.time() - start_time
        return result

    # ── Step 2: FETCH and CLEAN pages ────────────────────────────
    logger.info("[Step 2/4] Fetching and cleaning pages...")
    page_contents = []   # For LLM extraction
    page_metadata = []   # For the schema's page_metadata field

    # Select only the best pages to send to the LLM:
    #   - Homepage (for overview/contact info)
    #   - Top-scoring ADMISSIONS page
    #   - Top-scoring TUITION page
    # This keeps token usage within Groq free tier limits.
    best_admissions = None
    best_tuition = None
    for page in discovered_pages:
        if page.category == "ADMISSIONS" and (best_admissions is None or page.score > best_admissions.score):
            best_admissions = page
        if page.category == "TUITION" and (best_tuition is None or page.score > best_tuition.score):
            best_tuition = page

    pages_to_fetch = [{"url": domain_url, "category": "HOMEPAGE"}]
    if best_admissions:
        pages_to_fetch.append({"url": best_admissions.url, "category": "ADMISSIONS"})
        logger.info(f"  Best admissions page: {best_admissions.url} (score={best_admissions.score:.1f})")
    if best_tuition:
        pages_to_fetch.append({"url": best_tuition.url, "category": "TUITION"})
        logger.info(f"  Best tuition page: {best_tuition.url} (score={best_tuition.score:.1f})")

    # Deduplicate by URL
    seen_urls = set()
    unique_pages = []
    for page in pages_to_fetch:
        if page["url"] not in seen_urls:
            seen_urls.add(page["url"])
            unique_pages.append(page)

    for page_info in unique_pages:
        url = page_info["url"]
        category = page_info["category"]

        fetch_result = fetch_page(url)

        if not fetch_result.success or not fetch_result.html:
            logger.warning(f"Skipping {url}: {fetch_result.error}")
            continue

        # Clean the HTML
        cleaned_text = clean_html(fetch_result.html)
        title = extract_page_title(fetch_result.html)

        if not cleaned_text.strip():
            logger.warning(f"No usable text from {url}, skipping")
            continue

        page_contents.append({
            "url": url,
            "category": category,
            "cleaned_text": cleaned_text,
        })

        # Build metadata for this page
        page_metadata.append(PageMetadata(
            url=url,
            page_title=title,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            status_code=str(fetch_result.status_code),
        ))

        result.pages_fetched += 1
        logger.info(f"  [{category}] Cleaned {len(cleaned_text)} chars from: {url}")

    if not page_contents:
        result.error = "No pages could be fetched and cleaned"
        logger.error(f"No usable page content for {domain_url}")
        result.elapsed_time = time.time() - start_time
        return result

    # ── Step 3: LLM EXTRACTION ───────────────────────────────────
    logger.info(f"[Step 3/4] Extracting structured data via LLM ({len(page_contents)} pages)...")

    try:
        extracted_data = extract_university_data(page_contents, domain_url)

        if not extracted_data:
            result.error = "LLM extraction returned empty result"
            logger.error(f"LLM returned empty for {domain_url}")
            result.elapsed_time = time.time() - start_time
            return result

        # Build and validate the Pydantic model
        university_data = build_university_data(extracted_data, page_metadata)

    except Exception as e:
        result.error = f"LLM extraction failed: {e}"
        logger.error(f"LLM extraction failed for {domain_url}: {e}")
        result.elapsed_time = time.time() - start_time
        return result

    # ── Step 4: VALIDATE and SAVE ────────────────────────────────
    logger.info("[Step 4/4] Validating and saving output...")

    # Data quality checks
    quality_warnings = _run_quality_checks(university_data)
    result.quality_warnings = quality_warnings
    for warning in quality_warnings:
        logger.warning(f"  Quality: {warning}")

    # Count populated fields
    populated, total = _count_populated_fields(university_data)
    result.fields_populated = populated
    result.fields_total = total

    # Save to JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = sanitize_filename(domain_url) + ".json"
    output_path = os.path.join(OUTPUT_DIR, filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(university_data.model_dump_json(indent=2))

    result.output_file = output_path
    result.success = True
    result.university_name = (
        university_data.overview.university_name
        if university_data.overview else None
    )
    result.tuition_items = len(university_data.tuition_breakdown)
    result.deadlines = len(university_data.admission_deadlines)

    elapsed = time.time() - start_time
    result.elapsed_time = elapsed

    logger.info(f"Output saved to: {output_path}")
    logger.info(
        f"Pipeline complete for {domain_url} in {elapsed:.1f}s — "
        f"{populated}/{total} fields populated, "
        f"{len(quality_warnings)} quality warnings"
    )

    return result


def run_batch(domain_urls: list) -> List[PipelineResult]:
    """
    Process multiple university domains sequentially.

    Args:
        domain_urls: List of university domain URLs.

    Returns:
        List of PipelineResult for each domain.
    """
    logger.info(f"Starting batch run for {len(domain_urls)} universities")
    batch_start = time.time()

    results = []
    for i, url in enumerate(domain_urls, 1):
        logger.info(f"\n[{i}/{len(domain_urls)}] Processing: {url}")
        result = run_pipeline(url)
        results.append(result)

    batch_elapsed = time.time() - batch_start

    # Print batch summary
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH COMPLETE — {successful} succeeded, {failed} failed in {batch_elapsed:.1f}s")
    logger.info(f"{'='*60}")

    for r in results:
        status = "✓" if r.success else "✗"
        name = r.university_name or "Unknown"
        logger.info(
            f"  {status} {name} ({r.domain_url}) — "
            f"{r.pages_fetched} pages, "
            f"{r.tuition_items} tuition items, "
            f"{r.deadlines} deadlines, "
            f"{r.fields_populated}/{r.fields_total} fields, "
            f"{len(r.quality_warnings)} warnings"
        )
        if r.error:
            logger.info(f"    Error: {r.error}")

    return results


def _run_quality_checks(data: UniversityData) -> List[str]:
    """
    Run data quality checks on the extracted university data.

    Checks:
        - University name should not be null
        - At least one tuition item expected
        - Tuition costs should be reasonable (100 - 200,000)
        - Deadline dates should not be empty strings
        - No duplicate tuition items

    Returns:
        List of warning strings.
    """
    warnings = []

    # Check university name
    if not data.overview or not data.overview.university_name:
        warnings.append("Missing university name")

    # Check tuition
    if not data.tuition_breakdown:
        warnings.append("No tuition items extracted")
    else:
        seen_fees = set()
        for item in data.tuition_breakdown:
            # Reasonable cost range check
            if item.cost is not None:
                if item.cost < 100 or item.cost > 200000:
                    warnings.append(
                        f"Suspicious tuition cost: {item.fee_type} = {item.cost}"
                    )
            # Duplicate check
            fee_key = (item.fee_type, item.cost)
            if fee_key in seen_fees:
                warnings.append(f"Duplicate tuition item: {item.fee_type}")
            seen_fees.add(fee_key)

    # Check deadlines
    if not data.admission_deadlines:
        warnings.append("No admission deadlines extracted")
    else:
        for dl in data.admission_deadlines:
            if dl.deadline_date is not None and dl.deadline_date.strip() == "":
                warnings.append(
                    f"Empty deadline date for: {dl.deadline_type}"
                )

    # Check contact info
    if data.overview and data.overview.contact:
        if not data.overview.contact.phone and not data.overview.contact.email:
            warnings.append("No contact information (phone or email) found")

    return warnings


def _count_populated_fields(data: UniversityData) -> tuple:
    """
    Count how many fields in the schema are populated vs total.

    Returns:
        (populated_count, total_count)
    """
    total = 0
    populated = 0

    # Overview fields
    if data.overview:
        fields = [
            data.overview.university_name,
        ]
        if data.overview.location:
            fields.extend([
                data.overview.location.city,
                data.overview.location.state,
                data.overview.location.country,
                data.overview.location.postal_code,
            ])
        else:
            fields.extend([None, None, None, None])

        if data.overview.contact:
            fields.extend([
                data.overview.contact.phone,
                data.overview.contact.email,
            ])
        else:
            fields.extend([None, None])

        total += len(fields)
        populated += sum(1 for f in fields if f is not None)
    else:
        total += 7  # All overview fields missing

    # Tuition (count as 1 populated if at least one item exists)
    total += 1
    if data.tuition_breakdown:
        populated += 1

    # Deadlines (count as 1 populated if at least one item exists)
    total += 1
    if data.admission_deadlines:
        populated += 1

    return (populated, total)
