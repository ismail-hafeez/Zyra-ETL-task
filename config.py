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