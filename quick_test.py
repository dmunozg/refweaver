"""Quick test for RefWeaver - evaluates fewer articles for faster results."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from loguru import logger

from refweaver.analyzer import SentenceAnalyzer
from refweaver.dedup import deduplicate_articles
from refweaver.enrich import ArticleEnricher
from refweaver.models import Article
from refweaver.search import UnifiedSearch
from tests.fixtures import sample_texts

# Configure logging
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

# Initialize components
analizador = SentenceAnalyzer()
searcher = UnifiedSearch()
enricher = ArticleEnricher(use_llm_extractor=True)

# Analyze the paragraph
analized_sentences = analizador.analyze_paragraph(sample_texts.SHORT_SAMPLE)

# Focus on the sentence about Greenland ice sheet
target_sentence = analized_sentences[1]
print(f"\n{'='*60}")
print(f"TARGET: {target_sentence.text}")
print(f"{'='*60}\n")

# Generate keywords
keywords = analizador.generate_search_keywords(target_sentence)
print(f"Keywords: {keywords}\n")

# Search - LIMITED to 5 per keyword for speed
articles_found: list[Article] = []
for keyword in keywords:
    logger.info(f"Searching: '{keyword}'")
    partial_results = searcher.search(keyword, limit=5)
    logger.info(f"Found {len(partial_results)} articles\n")
    articles_found.extend(partial_results)

# Deduplicate and sort
articles_found = deduplicate_articles(articles_found)
logger.info(f"Total unique articles: {len(articles_found)}")

# Sort by citations (most cited first)
articles_found.sort(key=lambda a: -(a.citation_count or 0))

# Take top 5 for quick evaluation
articles_to_evaluate = articles_found[:5]
logger.info(f"Evaluating top {len(articles_to_evaluate)} articles\n")

# Evaluate each article
results = []
for i, article in enumerate(articles_to_evaluate, 1):
    print(f"\n[{i}/{len(articles_to_evaluate)}] {article.title[:50]}...")
    print(f"    Year: {article.year}, Citations: {article.citation_count}, OA: {article.open_access}")
    
    # Enrich if no abstract
    if article.abstract is None:
        article = enricher.fill_abstract(article=article, try_llm=True)
    
    # Evaluate
    assessment = analizador.evaluate_article_with_landing_page(
        sentence=target_sentence, 
        article=article,
        fetch_fulltext=True,
        try_alternative_pdf_sources=True,
    )
    
    verdict = assessment.get("verdict", "UNKNOWN")
    confidence = assessment.get("confidence", 0.0)
    source = assessment.get("evaluation_source", "unknown")
    
    print(f"    -> {verdict} (conf: {confidence:.2f}, src: {source})")
    
    if verdict in ("SUPPORTS", "PARTIALLY_SUPPORTS"):
        results.append({"article": article, "assessment": assessment})

# Summary
print(f"\n{'='*60}")
print(f"RESULTS: {len(results)} relevant articles found")
print(f"{'='*60}")

for i, result in enumerate(results, 1):
    article = result["article"]
    assessment = result["assessment"]
    print(f"\n{i}. {article.title}")
    print(f"   Verdict: {assessment['verdict']} ({assessment['confidence']:.2f})")
    print(f"   Reasoning: {assessment['reasoning'][:200]}...")
    if assessment.get('suggested_modification'):
        print(f"   Suggested: {assessment['suggested_modification']}")

if not results:
    print("\nNo supporting articles found in top 5. Try running full test with more articles.")
