"""
This module contains the main pipeline for the ETL process.     
"""
import bs4
import requests
from openai import OpenAI
import os
from typing import Generator

PATH='./data/university_domains.txt'

def get_domain() -> Generator[str, None, None]:
    with open(PATH, 'r') as f:
        urls = f.read().splitlines()
    for url in urls:
        yield url