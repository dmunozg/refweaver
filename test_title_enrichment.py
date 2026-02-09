"""Test title-based enrichment for Perplexity articles."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

from refweaver.adapters.perplexity import PerplexityAdapter
from refweaver.enrich import ArticleEnricher

# Load environment variables
load_dotenv()

# Configure logging
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

print("=" * 60)
print("Test: Title-based enrichment for Perplexity articles")
print("=" * 60)

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("Error: OPENROUTER_API_KEY not found in .env")
    exit(1)

# Initialize adapter and enricher
adapter = PerplexityAdapter(api_key=api_key, model="perplexity/sonar-pro")
enricher = ArticleEnricher()

# Search for articles
query = "Greenland ice sheet mass loss 2002-2016 GRACE"
print(f"\nSearching Perplexity: {query}\n")

articles = adapter.search(query, limit=5)
print(f"Found {len(articles)} articles\n")

# Show before/after for each article
for i, article in enumerate(articles, 1):
    print(f"\n{'='*60}")
    print(f"Article {i}: {article.title}")
    print(f"{'='*60}")

    print(f"\nBEFORE enrichment:")
    print(f"  Source: {article.source}")
    print(f"  Title: {article.title}")
    print(f"  DOI: {article.doi or 'None'}")
    print(f"  Authors: {article.authors if article.authors else 'None'}")
    print(f"  Year: {article.year or 'None'}")
    print(f"  Journal: {article.journal or 'None'}")
    print(f"  Abstract: {'Yes' if article.abstract else 'No'}")

    if not article.doi:
        print(f"\nAttempting title-based enrichment...")
        enriched = enricher.enrich_from_title(article, similarity_threshold=0.95)

        if enriched != article:
            print(f"\nAFTER enrichment:")
            print(f"  Source: {enriched.source}")
            print(f"  Title: {enriched.title}")
            print(f"  DOI: {enriched.doi or 'None'}")
            print(f"  Authors: {enriched.authors if enriched.authors else 'None'}")
            print(f"  Year: {enriched.year or 'None'}")
            print(f"  Journal: {enriched.journal or 'None'}")
            print(f"  Abstract: {'Yes' if enriched.abstract else 'No'}")

            # Show BibTeX
            print(f"\nBibTeX:")
            print(enriched.to_bibtex())
        else:
            print(f"\nNo match found (similarity < 0.95)")
    else:
        print(f"\nSkipping title search - article already has DOI")

print(f"\n{'='*60}")
print("Test complete!")
print(f"{'='*60}")
