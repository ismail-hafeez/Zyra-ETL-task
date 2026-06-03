# Zyra ETL Pipeline

An ETL pipeline that takes a university domain as input, automatically discovers relevant Admissions and Tuition/Cost pages, and extracts structured data into a validated Pydantic schema.

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/Zyra-ETL-task.git
cd Zyra-ETL-task

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your Groq API key
```

## Run Instructions

```bash
# Process a single university
python -m src.main --url https://www.bucknell.edu

# Process all domains from a file
python -m src.main --file data/university_domains.txt

# Process all 3 test universities
python -m src.main --all
```

Output JSON files are saved to `data/output/`.

### Run Tests

```bash
pytest tests/ -v
```

## Overall Approach

The pipeline follows a classic **Extract → Transform → Load** pattern:

1. **Extract (Crawl):** Starting from the given domain URL, a BFS crawler (max depth 2) discovers relevant pages. It uses keyword matching on URL paths and anchor text to identify Admissions and Tuition pages — no hardcoded URLs.

2. **Transform (Clean + Extract):** Raw HTML is cleaned by stripping noise elements (`<script>`, `<nav>`, `<footer>`, etc.) while preserving table structures. The cleaned text from the homepage, best admissions page, and best tuition page is sent to Groq's Llama 3.3 70B model in a single API call with JSON mode enabled.

3. **Load (Validate + Save):** The LLM's JSON response is parsed into Pydantic models, validated for type correctness, checked for data quality issues, and saved as structured JSON output.

## Architecture

```
main.py (CLI) → pipeline.py (orchestrator)
                    ├── crawlers/discovery.py  → Find relevant pages
                    │       └── crawlers/fetcher.py  → HTTP with retries
                    ├── src/utils.py           → Clean HTML, extract text
                    ├── src/llm_extractor.py   → Groq LLM structured extraction
                    └── schema.py              → Pydantic validation
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Keyword-based URL discovery** | University URLs follow predictable patterns (`/admissions`, `/tuition`, `/cost-of-attendance`). Keyword matching is fast, free, deterministic, and testable — no LLM needed for this step. |
| **Single LLM call per university** | Combining all page content into one request is faster (1 API call vs 5+), cheaper (less token overhead), and produces more consistent results since the model sees full context. |
| **Groq JSON mode** | `response_format={"type": "json_object"}` guarantees valid JSON output, eliminating fragile string parsing. Direct Pydantic validation from the response. |
| **HTML noise stripping** | Removing `<nav>`, `<footer>`, `<script>`, etc. before sending to the LLM maximizes signal-to-noise ratio in the limited context window. |
| **Table preservation** | Tuition data is often in `<table>` elements. Tables are converted to pipe-delimited text (`| Fee | Cost |`) so the LLM can understand tabular structure. |
| **Top 3 pages only** | Sending homepage + best admissions + best tuition page keeps token usage within free tier limits while covering all required data categories. |

## Assumptions and Limitations

- **English-only:** Assumes university websites are in English.
- **US-centric defaults:** Defaults to "USD" currency for US universities.
- **Max depth 2:** Deeply nested pages (3+ clicks from homepage) won't be discovered.
- **No JavaScript rendering:** Uses `requests` (no browser). Some JS-heavy sites may have limited content in raw HTML.
- **No PDF extraction:** As specified, PDF documents are skipped.
- **Free tier limits:** Groq's free tier has daily token limits. Text is truncated to ~6000 chars per page to stay within bounds.
- **Contact info depends on page content:** If phone/email isn't on the homepage, admissions page, or tuition page, it won't be captured.

## How AI/LLM Components Are Used

**Model:** Llama 3.3 70B Versatile via Groq API (OpenAI-compatible endpoint)

**Purpose:** Structured data extraction from scraped HTML text. The LLM receives:
- Cleaned text from 3 pages (homepage, admissions, tuition)
- A JSON schema template defining the expected output structure
- Strict extraction rules (no fabrication, null for missing data)

**Configuration:**
- `response_format={"type": "json_object"}` for guaranteed JSON output
- `temperature=0.1` for deterministic, consistent extraction
- Confidence scoring included in the same call

**What the LLM does NOT do:**
- Page discovery (handled by keyword matching)
- HTML parsing (handled by BeautifulSoup)
- Data validation (handled by Pydantic)

## Bonus Features Implemented

- ✅ **Automated tests** — pytest suite covering schemas, crawler logic, and extractors
- ✅ **Retry and error-handling** — Exponential backoff (3 attempts), auth-page skipping, graceful failure handling
- ✅ **Structured logging** — Timestamped logs at every pipeline stage with timing info
- ✅ **Data quality checks** — Missing fields, suspicious costs, duplicates, empty dates
- ✅ **Confidence scoring** — LLM rates extraction confidence (0-1) per field
- ✅ **Multiple domains** — Batch processing via `--all` or `--file` flags