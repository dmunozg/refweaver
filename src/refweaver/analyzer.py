"""Sentence analysis pipeline for RefWeaver.

Analyzes sentences from manuscript paragraphs to determine if they need references,
generates search keywords, and evaluates article relevance.
"""


from loguru import logger

from refweaver.llm import LLMClient
from refweaver.models import Article, Sentence
from refweaver.text_utils import split_sentences


class SentenceAnalyzer:
    """Analyzes sentences to determine if they need references."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize the sentence analyzer.

        Args:
            llm_client: LLM client for analysis. If None, creates a new instance.
        """
        self.llm = llm_client or LLMClient()
        logger.info("SentenceAnalyzer initialized")

    def analyze_paragraph(self, paragraph: str) -> list[Sentence]:
        """Analyze all sentences in a paragraph.

        Args:
            paragraph: Paragraph text to analyze.

        Returns:
            List of Sentence objects with reference analysis.
        """
        sentences = split_sentences(paragraph)
        results: list[Sentence] = []

        for sent_text in sentences:
            analysis = self.llm.analyze_sentence_needs_reference(
                sentence=sent_text,
                context=paragraph,
            )
            sentence = Sentence(
                text=sent_text,
                needs_reference=bool(analysis["needs_reference"]),
                reason=str(analysis["reason"]),
            )
            results.append(sentence)
            logger.debug(
                f"Analyzed: '{sent_text[:50]}...' -> "
                f"needs_reference={sentence.needs_reference}"
            )

        logger.info(f"Analyzed {len(results)} sentences in paragraph")
        return results

    def analyze_sentences(self, text: str) -> list[Sentence]:
        """Analyze all sentences in a text (paragraphs are processed together).

        This is a convenience method that splits text into paragraphs,
        then analyzes all sentences across all paragraphs.

        Args:
            text: Full text to analyze (can be multiple paragraphs).

        Returns:
            List of Sentence objects with reference analysis.
        """
        from refweaver.text_utils import split_paragraphs

        paragraphs = split_paragraphs(text)
        all_sentences: list[Sentence] = []

        for para in paragraphs:
            sentences = self.analyze_paragraph(para)
            all_sentences.extend(sentences)

        logger.info(f"Analyzed {len(all_sentences)} sentences total")
        return all_sentences

    def generate_search_keywords(self, sentence: str | Sentence) -> list[str]:
        """Generate search keywords for finding supporting articles.

        Uses LLM with structured output to extract key concepts and terms
        from a sentence for effective academic search queries.

        Args:
            sentence: The sentence needing reference support (str or Sentence object).

        Returns:
            List of search keyword strings optimized for academic search.
        """
        # Extract text if Sentence object is passed
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        # Delegate to LLM client which uses pydantic-ai structured output
        return self.llm.generate_search_keywords(sentence_text)

    async def generate_search_keywords_async(self, sentence: str | Sentence) -> list[str]:
        """Async version of generate_search_keywords."""
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence
        return await self.llm.generate_search_keywords_async(sentence_text)

    def evaluate_article_relevance(
        self,
        sentence: str | Sentence,
        article: Article,
    ) -> dict[str, str | float | None]:
        """Evaluate if an article is relevant to support a sentence (abstract only).

        First-pass evaluation using abstract. Returns a verdict on how the
        article relates to the claim.

        Args:
            sentence: The claim needing support (str or Sentence object).
            article: The candidate article to evaluate.

        Returns:
            Dict with 'verdict' (str: SUPPORTS/CONTRADICTS/PARTIALLY_SUPPORTS/
            INSUFFICIENT_INFO/NOT_RELEVANT), 'confidence' (float), 'reasoning' (str),
            and 'suggested_modification' (str | None).
        """
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        return self.llm.evaluate_article_relevance(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )

    async def evaluate_article_relevance_async(
        self,
        sentence: str | Sentence,
        article: Article,
    ) -> dict[str, str | float | None]:
        """Async version of evaluate_article_relevance (abstract only)."""
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        return await self.llm.evaluate_article_relevance_async(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )

    def evaluate_article_relevance_fulltext(
        self,
        sentence: str | Sentence,
        article: Article,
        fulltext_content: str,
    ) -> dict[str, str | float | None]:
        """Evaluate article relevance using full text (e.g., from PDF).

        This provides a more thorough evaluation when the full PDF is available.

        Args:
            sentence: The claim needing support.
            article: The candidate article to evaluate.
            fulltext_content: Extracted text from the PDF.

        Returns:
            Dict with 'verdict', 'confidence', 'reasoning', 'suggested_modification'.
        """
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        return self.llm.evaluate_article_relevance_fulltext(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            fulltext_content=fulltext_content,
        )

    async def evaluate_article_relevance_fulltext_async(
        self,
        sentence: str | Sentence,
        article: Article,
        fulltext_content: str,
    ) -> dict[str, str | float | None]:
        """Async version of evaluate_article_relevance_fulltext."""
        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        return await self.llm.evaluate_article_relevance_fulltext_async(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            fulltext_content=fulltext_content,
        )

    def evaluate_article_with_landing_page(
        self,
        sentence: str | Sentence,
        article: Article,
        fetch_fulltext: bool = True,
        try_alternative_pdf_sources: bool = True,
        unpaywall_email: str | None = None,
    ) -> dict[str, str | float | None]:
        """Multi-pass article evaluation: abstract -> landing page -> PDF.

        Phase 1: Evaluate using abstract
        Phase 2: If verdict is INSUFFICIENT_INFO/PARTIALLY_SUPPORTS and article
            is open access, fetch landing page and re-evaluate
        Phase 3: If still insufficient, try to get PDF (including alternative
            sources like Unpaywall, Anna's Archive) and re-evaluate

        Args:
            sentence: The claim needing support (str or Sentence object).
            article: The candidate article to evaluate.
            fetch_fulltext: Whether to attempt fetching full text when needed.
            try_alternative_pdf_sources: Whether to try Unpaywall, Anna's Archive, etc.
            unpaywall_email: Email for Unpaywall API (optional but recommended).

        Returns:
            Dict with 'verdict', 'confidence', 'reasoning', 'suggested_modification',
            and 'evaluation_source' ("abstract", "landing_page", or "pdf").
        """
        from refweaver.pdf_extract import try_get_fulltext_from_pdf
        from refweaver.web_fetch import fetch_article_landing_page

        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        # Phase 1: Evaluate using abstract
        result = self.llm.evaluate_article_relevance(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )
        result["evaluation_source"] = "abstract"

        if not fetch_fulltext:
            return result

        verdict = result.get("verdict", "")

        # Phase 2: Try landing page if needed
        if verdict in ("INSUFFICIENT_INFO", "PARTIALLY_SUPPORTS"):
            logger.info(
                f"Verdict is {verdict}, attempting landing page fetch "
                f"for: {article.title[:50]}..."
            )

            landing_page_text = fetch_article_landing_page(article, use_selenium=True)

            if landing_page_text:
                logger.info(
                    f"Re-evaluating with landing page content "
                    f"({len(landing_page_text)} chars)"
                )
                result = self.llm.evaluate_article_relevance_fulltext(
                    sentence=sentence_text,
                    article_title=article.title,
                    article_authors=article.authors,
                    article_year=article.year,
                    fulltext_content=landing_page_text,
                )
                result["evaluation_source"] = "landing_page"
                verdict = result.get("verdict", "")
            else:
                logger.warning(
                    f"Could not fetch landing page for: {article.title[:50]}..."
                )

        # Phase 3: Try PDF if still needed (including alternative sources)
        if verdict in ("INSUFFICIENT_INFO", "PARTIALLY_SUPPORTS"):
            logger.info(
                f"Verdict still {verdict}, attempting PDF download "
                f"for: {article.title[:50]}..."
            )

            pdf_text = try_get_fulltext_from_pdf(
                article,
                try_alternative_sources=try_alternative_pdf_sources,
                email=unpaywall_email,
            )

            if pdf_text:
                logger.info(f"Re-evaluating with PDF content ({len(pdf_text)} chars)")
                # Limit PDF text to avoid token limits
                limited_text = pdf_text[:50000]  # ~50k chars should be plenty
                result = self.llm.evaluate_article_relevance_fulltext(
                    sentence=sentence_text,
                    article_title=article.title,
                    article_authors=article.authors,
                    article_year=article.year,
                    fulltext_content=limited_text,
                )
                result["evaluation_source"] = "pdf"
            else:
                logger.warning(f"Could not download PDF for: {article.title[:50]}...")

        return result

    async def evaluate_article_with_landing_page_async(
        self,
        sentence: str | Sentence,
        article: Article,
        fetch_fulltext: bool = True,
    ) -> dict[str, str | float | None]:
        """Async version of evaluate_article_with_landing_page."""
        from refweaver.web_fetch import fetch_article_landing_page_async

        sentence_text = sentence.text if isinstance(sentence, Sentence) else sentence

        # Phase 1: Evaluate using abstract
        result = await self.llm.evaluate_article_relevance_async(
            sentence=sentence_text,
            article_title=article.title,
            article_authors=article.authors,
            article_year=article.year,
            article_abstract=article.abstract,
        )
        result["evaluation_source"] = "abstract"

        # Phase 2: If needed and possible, fetch landing page and re-evaluate
        if fetch_fulltext and article.open_access:
            verdict = result.get("verdict", "")
            if verdict in ("INSUFFICIENT_INFO", "PARTIALLY_SUPPORTS"):
                logger.info(
                    f"Verdict is {verdict}, attempting async landing page fetch "
                    f"for: {article.title[:50]}..."
                )

                landing_page_text = await fetch_article_landing_page_async(article)

                if landing_page_text:
                    logger.info(
                        f"Re-evaluating with landing page content "
                        f"({len(landing_page_text)} chars)"
                    )
                    fulltext_result = await self.llm.evaluate_article_relevance_fulltext_async(
                        sentence=sentence_text,
                        article_title=article.title,
                        article_authors=article.authors,
                        article_year=article.year,
                        fulltext_content=landing_page_text,
                    )
                    fulltext_result["evaluation_source"] = "fulltext"
                    return fulltext_result
                else:
                    logger.warning(
                        f"Could not fetch landing page for: {article.title[:50]}..."
                    )

        return result
