"""Test title-based enrichment with debug output."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

from refweaver.adapters.perplexity import PerplexityAdapter
from refweaver.adapters.openalex import OpenAlexAdapter
from refweaver.dedup import title_similarity, merge_articles

# Load environment variables
load_dotenv()

# Configure logging
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

print("=" * 60)
print("Test: Title-based enrichment with debug")
print("=" * 60)

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("Error: OPENROUTER_API_KEY not found")
    exit(1)

# Initialize adapters
perplexity = PerplexityAdapter(api_key=api_key, model="perplexity/sonar-pro")
openalex = OpenAlexAdapter()

# Get articles from Perplexity
query = "Mass balance of the Greenland ice sheet"
print(f"\n1. Searching Perplexity: {query}\n")

articles = perplexity.search(query, limit=3)
print(f"Found {len(articles)} articles\n")

# Test enrichment on the first article that doesn't have a DOI
for article in articles:
    if article.doi:
        print(f"Skipping (has DOI): {article.title}")
        continue

    print(f"\n{'='*60}")
    print(f"Testing enrichment for: {article.title}")
    print(f"{'='*60}")

    # Search OpenAlex
    print(f"\n2. Searching OpenAlex with title...")
    candidates = openalex.search(article.title, limit=5)
    print(f"   Found {len(candidates)} candidates\n")

    # Check similarity for each
    best_match = None
    best_sim = 0.0

    for i, candidate in enumerate(candidates, 1):
        if not candidate.title:
            continue

        sim = title_similarity(article.title, candidate.title)
        print(f"   [{i}] Similarity: {sim:.3f}")
        print(f"       Perplexity:  '{article.title[:70]}...'")
        print(f"       OpenAlex:    '{candidate.title[:70]}...'")
        print(f"       DOI: {candidate.doi or 'None'}")
        print()

        if sim > best_sim:
            best_sim = sim
            best_match = candidate

    # Try merging with best match at different thresholds
    if best_match:
        print(f"\n3. Best match similarity: {best_sim:.3f}")

        for threshold in [0.95, 0.90, 0.85, 0.80]:
            if best_sim >= threshold:
                print(f"\n   Threshold {threshold}: MATCH!")
                merged = merge_articles([article, best_match])

                print(f"\n   Original:")
                print(f"     DOI: {article.doi or 'None'}")
                print(f"     Authors: {len(article.authors) if article.authors else 0}")

                print(f"\n   Merged:")
                print(f"     DOI: {merged.doi or 'None'}")
                print(f"     Authors: {len(merged.authors) if merged.authors else 0}")
                print(f"     Year: {merged.year or 'None'}")
                print(f"     Journal: {merged.journal or 'None'}")

                print(f"\n   BibTeX:")
                print(merged.to_bibtex())
                break
            else:
                print(f"   Threshold {threshold}: No match")
    else:
        print(f"\n   No candidates found")

    # Only test first article for this demo
    break

print(f"\n{'='*60}")
print("Test complete!")
print(f"{'='*60}")
