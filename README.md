# Zyra-ETL-task
Build a simple ETL pipeline that, takes a university domain as input, automatically discovers relevant Admissions and Tuition/Cost pages and extracts structured data into the provided Pydantic schema.


## Requirements:
### Starting only from the provided domain:
•	Automatically identify relevant Admissions and Tuition/Cost pages.
•	Hardcoded destination URLs are not allowed.
•	Maximum crawl depth: 2.
•	Authentication-required pages should be ignored.
•	PDF extraction is not required.
•	JavaScript rendering is optional.

## Data Extraction:
### Extract and normalize information required by the provided schema, including:
•	University overview and contact information
•	Tuition breakdown
•	Admission deadlines
•	Optional Metadata for all pages used during extraction

## Data Quality:
•	All output must pass Pydantic validation.
•	Normalize values where appropriate.
•	Return `null` when information cannot be extracted with reasonable confidence.
•	Do not fabricate missing values.
•	(Optional) Include metadata for every page used as a source.

## Deliverables:
1. Source code
2. Sample output for the provided universities
3. A short README describing:
       - Installation and Run instructions
       - Overall approach
       - Key design decisions
       - Assumptions and limitations
       - How AI/LLM components are used (if applicable)

## Suggested Tools(not mandatory):
- Web scraping: requests, beautifulsoup4
- LLM: google-genai (free Gemini API)
- Schema validation: pydantic

## Output Schema
```python
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class Location(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class Contact(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class Overview(BaseModel):
    university_name: Optional[str] = None
    location: Optional[Location] = None
    contact: Optional[Contact] = None


class TuitionItem(BaseModel):
    fee_type: Optional[str] = None
    cost: Optional[int] = None
    currency: Optional[str] = None


class DeadlineType(str, Enum):
    EARLY_DECISION = "Early Decision"
    REGULAR_DECISION = "Regular Decision"
    TRANSFER_ADMISSION = "Transfer Admission"


class AdmissionDeadline(BaseModel):
    deadline_type: Optional[DeadlineType] = None
    deadline_date: Optional[str] = None
    notes: Optional[str] = None


class PageMetadata(BaseModel):
    url: Optional[str] = None
    page_title: Optional[str] = None
    scraped_at: Optional[str] = None
    status_code: Optional[str] = None


class UniversityData(BaseModel):
    overview: Optional[Overview] = None
    tuition_breakdown: List[TuitionItem] = []
    admission_deadlines: List[AdmissionDeadline] = []
    page_metadata: List[PageMetadata] = []
```

### Example Input Domain and  expected pages discoverable by the pipeline :
Input Domain: Bucknell University
Find Pages: Admissions, Tuition/Cost

Input Domain: University of the District of Columbia (UDC)
Find Pages: Admissions, Tuition/Cost

Input Domain: Salisbury University
Find pages: Admissions, Tuition/Cost

## Notes:
You are free to choose the architecture, tools, and extraction strategy. We are interested in your reasoning, tradeoffs, code quality, robustness, and ability to work with real-world web data.

## AI Engineer(Data) - Bonus Optional Tasks:
### Implement one or more of the following:
•	Basic automated tests for key components.
•	Retry and error-handling logic for failed requests.
•	Structured logging and execution summaries.
•	Data quality checks (e.g., missing required fields, invalid dates, duplicate records).
•	Confidence scoring or source attribution for extracted fields.
•	Support for processing multiple university domains in a single run.










