"""
This module contains helper functions for the ETL process.     
"""
import bs4
import requests
from openai import OpenAI
import os
from typing import Generator
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
API_KEY=os.getenv('GROQ_API')
PATH='./data/university_domains.txt'

def get_location(url: str) -> dict:
    """
    Fetches the location data from the given URL.
    """
    client = OpenAI(
        api_key=API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    prompt = f"""
    State the Country, city, state and postal code of the university in the following link: {url}
    Return ONLY the country, city, state and postal code.
    """
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile", 
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    ans=completion.choices[0].message.content

    # Get the answer and split it into components
    ans=ans.strip().split(", ")
    country = ans[0]
    city = ans[1]
    state = ans[2]
    postal_code = ans[3]

    return {
        "country": country,
        "city": city,
        "state": state,
        "postal_code": postal_code
    }

def get_domain() -> Generator[str, None, None]:
    with open(PATH, 'r') as f:
        urls = f.read().splitlines()
    for url in urls:
        yield url


