"""Test Perplexity adapter with Greenland ice sheet sample."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

from refweaver.adapters.perplexity import PerplexityAdapter
from tests.fixtures import sample_texts

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

# Get API key from environment
api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("Error: OPENROUTER_API_KEY not found in .env file or environment")
    exit(1)

# Initialize adapter with sonar-pro for better quality
adapter = PerplexityAdapter(api_key=api_key, model="perplexity/sonar-pro")

# Test with the SHORT_SAMPLE sentence about Greenland ice sheet
test_sentence = sample_texts.SHORT_SAMPLE.split('.')[1].strip() + '.'
print(f"Testing Perplexity adapter with query:\n  {test_sentence}\n")

try:
    articles = adapter.search(test_sentence, limit=10)

    print(f"Found {len(articles)} articles:\n")

    for i, article in enumerate(articles, 1):
        print(f"[{i}] {article.title}")
        print(f"    Source: {article.source}")
        print(f"    Year: {article.year or 'Unknown'}")
        print(f"    Authors: {', '.join(article.authors) if article.authors else 'Unknown'}")
        print(f"    DOI: {article.doi or 'Unknown'}")
        print(f"    URL: {article.url}")
        print(f"    Open Access: {article.open_access}")
        print()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
