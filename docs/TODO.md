# RefWeaver Project TODO & Status

## Date: 2026-02-06

---

## ✅ What We've Built

### Core Pipeline
1. **Text Processing** (`text_utils.py`)
   - Paragraph splitting (blank-line based)
   - Sentence tokenization (NLTK Punkt)
   - Preprocessing pipeline for manuscripts

2. **Sentence Analysis** (`analyzer.py`)
   - LLM-based analysis of whether sentences need references
   - Pydantic-ai structured output for reliability
   - Returns `Sentence` objects with `needs_reference`, `reason`

3. **Search Infrastructure** (`search.py`, `adapters/`)
   - Unified search across 3 sources: Semantic Scholar, OpenAlex, Google Scholar
   - **NEW: Perplexity Sonar fallback** (`perplexity.py`, `search_with_fallback.py`)
     - Uses OpenRouter for API access
     - Triggers when primary sources return <3 results
     - Parses citations from web-grounded responses
   - Automatic deduplication
   - Returns unified `Article` models

4. **Article Evaluation** (Multi-phase)
   - **Phase 1**: Abstract evaluation (5 verdicts: SUPPORTS/CONTRADICTS/PARTIALLY_SUPPORTS/INSUFFICIENT_INFO/NOT_RELEVANT)
   - **Phase 2**: Landing page fetch with Selenium (handles JS-heavy sites)
   - **Phase 3**: PDF extraction from multiple sources

5. **PDF Sources** (`pdf_sources.py`, `pdf_extract.py`)
   - Direct PDF URL from article
   - Unpaywall API (legal OA finder)
   - Anna's Archive (shadow library index)
   - Direct DOI resolution (arXiv, bioRxiv patterns)
   - PyMuPDF for text extraction

6. **Web Fetching** (`web_fetch.py`)
   - Selenium-based fetching (handles bot detection)
   - BeautifulSoup HTML text extraction
   - Fallback to requests if Selenium fails

7. **Article Enrichment** (`enrich.py`)
   - Cross-API abstract lookup
   - **NEW: CrossRef enrichment** - Query DOI for BibTeX metadata (authors, journal, volume, pages, publisher)
   - LLM-based web extraction
   - Selenium fallback for 403-blocked sites

### Data Models (`models.py`)
- `Article`: Unified model with DOI, authors, year, abstract, PDF URL, open_access flag
- **NEW: BibTeX support** - `entry_type` field for @article/@misc/etc., `to_bibtex()` method
- **NEW: CrossRef enrichment** - `enrich_from_crossref()` method for DOI-based metadata lookup
- `Sentence`: Text + `needs_reference` boolean + reason
- All Pydantic-based, immutable

### Citation Export (`bibtex.py`)
- Export articles to `.bib` files
- `export_to_bibtex()` - Export list of articles
- `export_analysis_results()` - Export analysis results with verdict notes

### LLM Integration (`llm.py`)
- Pydantic-ai based with structured output
- Models: SearchKeywords, SentenceAnalysis, ArticleRelevance, ExtractedAbstract
- Auto-detection from vLLM/OpenAI-compatible APIs
- Async support

---

## 🔍 Test Results (2026-02-06)

### Greenland Ice Sheet Sentence Test
**Target**: "The Greenland ice sheet lost approximately 280 gigatons of mass per year between 2002 and 2016."

**Keywords Generated**:
- 'Greenland ice sheet mass loss'
- 'GRACE satellite data' / 'Annual mass loss rate'
- '2002-2016'

**Search Results**:
- Found 39-45 unique articles across all keywords
- Mix of open access and closed access

**Verdicts Observed**:
- `CONTRADICTS` (confidence: 0.95) - Some articles disagree with the claim
- `INSUFFICIENT_INFO` (confidence: 0.90-0.95) - Abstract/landing page doesn't have enough info
- `NOT_RELEVANT` (confidence: 1.00) - Article off-topic
- `SUPPORTS` - Not yet observed in limited test runs

**Issues Found**:
1. Many articles return `INSUFFICIENT_INFO` even after landing page fetch
2. PDF downloads often fail (rate limiting, bot detection)
3. Evaluation is slow (~30+ seconds per article due to LLM calls)

---

## ❌ Known Issues

1. **Evaluation Speed**: Each article takes 30+ seconds to evaluate through all 3 phases
2. **PDF Access**: Many PDF downloads fail despite multiple sources
3. **INSUFFICIENT_INFO**: Too many articles can't be evaluated even with full text
4. **No SUPPORTS found yet**: In limited testing, no articles have returned SUPPORTS verdict
5. **Google Scholar Rate Limiting**: Often returns 403, requires Selenium fallback
6. **Landing Page Quality**: Selenium fetches work but often get paywalled content

---

## 📝 TODO Items

### High Priority

1. **Improve Article Finding**
   - [x] **Perplexity fallback adapter** - Created `PerplexityAdapter` using OpenRouter
   - [x] **Unified search with fallback** - `UnifiedSearchWithFallback` triggers Perplexity when primary sources return <3 results
   - [x] **BibTeX export** - `to_bibtex()` method and `export_to_bibtex()` utility
   - [x] **CrossRef enrichment** - `enrich_from_crossref()` for DOI-based metadata
   - [ ] Increase search limits beyond 15/keyword
   - [ ] Add more specific keywords for quantitative claims (e.g., include "280 Gt")
   - [ ] Try different keyword combinations
   - [ ] Consider searching for specific papers (GRACE mission results)

2. **Better PDF Access**
   - [ ] Implement proper rate limiting between requests
   - [ ] Add retry logic with exponential backoff
   - [ ] Try Sci-Hub integration (legal gray area)
   - [ ] Consider Z-Library / LibGen as additional sources
   - [ ] Check if institutional access would help

3. **Optimize Evaluation Speed**
   - [ ] Batch LLM calls where possible
   - [ ] Cache evaluation results
   - [ ] Parallelize article evaluation
   - [ ] Skip Phase 2/3 if abstract is clearly relevant/irrelevant

4. **Improve Verdict Accuracy**
   - [ ] Fine-tune LLM prompts for better differentiation
   - [ ] Add example few-shots in prompts
   - [ ] Consider fine-tuned model instead of general-purpose LLM
   - [ ] Add citation matching (check if sentence already cites the paper)

### Medium Priority

5. **User Interface**
   - [ ] CLI interface for manuscript input
   - [ ] Progress bars for long operations
   - [ ] Better formatting of results
   - [ ] Export to BibTeX/RIS

6. **Citation Management**
   - [ ] Integrate with Zotero/Mendeley
   - [ ] Generate formatted citations
   - [ ] Check for existing citations in manuscript

7. **Testing**
   - [ ] Unit tests for all new PDF source resolvers
   - [ ] Integration tests with real APIs
   - [ ] Mock tests for faster CI

### Low Priority

8. **Performance**
   - [ ] Async throughout entire pipeline
   - [ ] Connection pooling for HTTP requests
   - [ ] Redis caching for article metadata

9. **Documentation**
   - [ ] API documentation
   - [ ] Usage examples
   - [ ] Architecture diagrams

---

## 🎯 Next Steps (Recommended)

1. **Run full test overnight** with 50+ articles and capture all verdicts
2. **Analyze why INSUFFICIENT_INFO is so common** - check if prompts need work
3. **Try to find specific papers** about GRACE mission Greenland results
4. **Consider if the claim itself is too specific** - maybe it's from a specific paper that's hard to find
5. **Evaluate the LLM's accuracy** - manually check a few articles to see if verdicts make sense

---

## 💡 Ideas for Improvement

1. **Citation Matching**: Instead of searching, try to match against known citation databases
2. **Semantic Search**: Use embeddings to find semantically similar papers
3. **Author Matching**: If we know the likely authors, search by author name
4. **Year Filtering**: The claim mentions 2002-2016, prioritize papers from 2016-2020
5. **Journal Targeting**: Look specifically at Nature, Science, JGR, GRL for this type of claim

---

## 📊 Current Test Coverage

- `test_text_utils.py`: 16 tests ✓
- `test_analyzer.py`: 19 tests ✓  
- `test_llm.py`: 10 tests ✓
- `test_models.py`: 6 tests ✓
- `test_semantic_scholar.py`: 10 tests ✓
- `test_web_fetch.py`: 11 tests ✓

**Total**: 72 tests passing

---

## 🔧 Files Created/Modified Today

- `src/refweaver/analyzer.py` - SentenceAnalyzer with multi-phase evaluation
- `src/refweaver/llm.py` - Pydantic-ai based LLM client
- `src/refweaver/web_fetch.py` - Selenium-based web fetching
- `src/refweaver/pdf_extract.py` - PDF text extraction
- `src/refweaver/pdf_sources.py` - Alternative PDF sources (Unpaywall, Anna's Archive)
- `src/refweaver/text_utils.py` - Text processing utilities
- `tests.py` - Main test script
- `quick_test.py` - Faster test script (5 articles)

---

*Status: Active development - core pipeline functional, needs refinement for production use*
