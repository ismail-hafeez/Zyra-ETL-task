"""
Configuration variables for the ETL pipeline.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Settings
GROQ_API_KEY = os.getenv("GROQ_API")
GROQ_BASE_URL = 'https://api.groq.com/openai/v1'
MODEL_NAME = "llama-3.3-70b-versatile"

# Crawler Settings
CRAWL_MAX_DEPTH = 2
REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
USER_AGENT = "Zyra-ETL-Bot/1.0 (Mozilla/5.0; compatible; Educational Research)"

# Keyword configuration for link discovery
ADMISSION_KEYWORDS = ["admission", "admissions", "apply", "deadline", "application"]
TUITION_KEYWORDS = ["tuition", "cost", "fee", "fees", "financial-aid", "cost-of-attendance", "financial aid"]

# The JSON schema template we send to the LLM
EXTRACTION_SCHEMA = """{
    "overview": {
        "university_name": "string or null",
        "location": {
            "city": "string or null",
            "state": "string or null",
            "country": "string or null",
            "postal_code": "string or null"
        },
        "contact": {
            "phone": "string or null",
            "email": "string (valid email) or null"
        }
    },
    "tuition_breakdown": [
        {
            "fee_type": "string describing the fee (e.g. 'Tuition - In State', 'Room and Board')",
            "cost": "integer (no dollar signs, no commas)",
            "currency": "string, e.g. 'USD'"
        }
    ],
    "admission_deadlines": [
        {
            "deadline_type": "one of: 'Early Decision', 'Regular Decision', 'Transfer Admission' or null",
            "deadline_date": "string in format 'YYYY-MM-DD' or 'Month Day, Year' or null",
            "notes": "string with any additional context or null"
        }
    ],
    "field_confidence": [
        {
            "field_name": "string (e.g. 'university_name', 'tuition_in_state')",
            "confidence": "float between 0.0 and 1.0",
            "source_url": "string URL where this data was found or null"
        }
    ]
}"""

SYSTEM_PROMPT = """You are a precise data extraction assistant specializing in university information.
Your job is to extract structured data from scraped university web page content.

CRITICAL RULES:
1. Extract ONLY from the provided text. Do NOT use your own knowledge.
2. Return null for any field you cannot confidently determine from the text.
3. Do NOT fabricate, guess, or hallucinate any values.
4. For 'cost', return an integer only (remove dollar signs, commas). Example: "$12,500" -> 12500
5. For 'currency', use "USD" for US universities unless stated otherwise.
6. For 'deadline_type', use EXACTLY one of: "Early Decision", "Regular Decision", "Transfer Admission". If the deadline doesn't match any of these, set deadline_type to null and describe it in notes.
7. For 'deadline_date', try to normalize to a readable date format.
8. For 'email', only include properly formatted email addresses.
9. For 'phone', include the full number with area code if available.
10. For 'field_confidence', rate your confidence (0.0 to 1.0) for each major field you extracted.

Return ONLY valid JSON matching the provided schema. No extra text, no markdown."""