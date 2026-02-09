"""Test BibTeX export and CrossRef enrichment."""

import os
import sys
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

from refweaver.adapters.perplexity import PerplexityAdapter
from refweaver.models import Article

# Load environment variables
load_dotenv()

# Configure logging
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

print("=" * 60)
print("Test 1: Article to BibTeX conversion")
print("=" * 60)

# Create a sample article
article = Article(
    source="test",
    external_id="test-123",
    entry_type="article",
    title="Mass balance of the Greenland and Antarctic ice sheets from 1992 to 2020",
    authors=["Horton, R. T. W. B.", "Shepherd, A.", "et al."],
    year=2023,
    month=3,
    journal="Earth System Science Data",
    volume="15",
    issue="4",
    pages="1597-1616",
    doi="10.5194/essd-15-1597-2023",
    publisher="Copernicus Publications",
)

print("\nBibTeX output:")
print(article.to_bibtex())

print("\n" + "=" * 60)
print("Test 2: Webpage (misc) to BibTeX")
print("=" * 60)

webpage = Article(
    source="perplexity",
    external_id="nasa-123",
    entry_type="misc",
    title="Greenland Ice Loss 2002-2016 - GRACE-FO",
    authors=["NASA"],
    year=2023,
    url="https://gracefo.jpl.nasa.gov/resources/33/greenland-ice-loss-2002-2016/",
    accessed_date=date.today(),
)

print("\nBibTeX output:")
print(webpage.to_bibtex(cite_key="NASA_GRACE_2023"))

print("\n" + "=" * 60)
print("Test 3: CrossRef enrichment via DOI")
print("=" * 60)

# Test with a known DOI
test_doi = "10.1002/2016GL069666"  # The Khan et al. paper from our earlier test

minimal_article = Article(
    source="perplexity",
    external_id=test_doi,
    entry_type="article",
    title="A high-resolution record of Greenland mass balance",
    authors=["Khan, S. A."],
    year=2016,
    doi=test_doi,
    url=f"https://doi.org/{test_doi}",
)

print("\nBefore enrichment:")
print(f"  Title: {minimal_article.title}")
print(f"  Authors: {minimal_article.authors}")
print(f"  Journal: {minimal_article.journal}")
print(f"  Volume: {minimal_article.volume}")
print(f"  Pages: {minimal_article.pages}")
print(f"  Publisher: {minimal_article.publisher}")

print("\nEnriching from CrossRef...")
enriched = minimal_article.enrich_from_crossref()

print("\nAfter enrichment:")
print(f"  Title: {enriched.title}")
print(f"  Authors: {enriched.authors}")
print(f"  Journal: {enriched.journal}")
print(f"  Volume: {enriched.volume}")
print(f"  Pages: {enriched.pages}")
print(f"  Publisher: {enriched.publisher}")

print("\nBibTeX output:")
print(enriched.to_bibtex())

print("\n" + "=" * 60)
print("Test 4: Perplexity search with BibTeX export")
print("=" * 60)

api_key = os.getenv("OPENROUTER_API_KEY")
if api_key:
    adapter = PerplexityAdapter(api_key=api_key, model="perplexity/sonar-pro")

    query = "Greenland ice sheet mass loss 2002-2016"
    print(f"\nSearching: {query}\n")

    articles = adapter.search(query, limit=3)

    print(f"Found {len(articles)} articles. BibTeX entries:\n")

    for i, article in enumerate(articles, 1):
        print(f"% Article {i}")
        print(article.to_bibtex())
        print()

        # Try to enrich if it has a DOI
        if article.doi:
            print(f"% Enriched version:")
            enriched = article.enrich_from_crossref()
            if enriched != article:
                print(enriched.to_bibtex())
            else:
                print("% (Enrichment failed or no new data)")
            print()
else:
    print("Skipping Perplexity test - no OPENROUTER_API_KEY found")
