"""LLM client configuration and utilities for RefWeaver using pydantic-ai.

Supports OpenAI-compatible APIs (vLLM, OpenAI, etc.) with structured output
via Pydantic models.
"""

import asyncio
import os
from typing import Any, cast

import requests
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from refweaver.retry import retry_call
from refweaver.timing import run_with_timeout


class LLMConfig:
    """Configuration for LLM client from environment variables."""

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:11435/v1")
        self.api_key = os.getenv("OPENAI_API_KEY", "not-needed")
        self.model = os.getenv("LLM_MODEL")  # Optional, will auto-detect if not set
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))

        logger.debug(f"LLMConfig initialized: base_url={self.base_url}, model={self.model}")

    def get_model(self) -> str:
        """Get the model name to use.

        If LLM_MODEL env var is set, returns that.
        Otherwise, fetches available models and returns the first one.

        Returns:
            Model name string.

        Raises:
            RuntimeError: If no models are available or API is unreachable.
        """
        if self.model:
            logger.info(f"Using configured model: {self.model}")
            return self.model

        # Auto-detect model by listing available models
        logger.info("LLM_MODEL not set, auto-detecting from /models endpoint...")

        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            models = data.get("data", [])
            if not models:
                raise RuntimeError("No models available from LLM server")

            # Get first model ID
            first_model = models[0].get("id")
            if not first_model:
                raise RuntimeError("First model has no ID")

            self.model = first_model
            logger.info(f"Auto-detected model: {self.model}")
            assert self.model is not None  # this feels dirty
            return self.model

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch models from {self.base_url}: {e}") from e
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format from /models endpoint: {e}") from e


# Output models for structured LLM responses


class SearchKeywords(BaseModel):
    """Structured output for search keyword generation."""

    keywords: list[str] = Field(
        ...,
        description="3-5 search keyword phrases for academic search",
        min_length=1,
        max_length=5,
    )


class SentenceAnalysis(BaseModel):
    """Structured output for sentence reference analysis."""

    needs_reference: bool = Field(
        ...,
        description="Whether this sentence requires a reference/citation",
    )
    reason: str = Field(
        ...,
        description="Explanation for why the sentence needs or doesn't need a reference",
    )


class ArticleRelevance(BaseModel):
    """Structured output for article relevance evaluation."""

    verdict: str = Field(
        ...,
        description=(
            "Assessment of how the article relates to the claim: "
            "SUPPORTS (evidence clearly backs the claim), "
            "CONTRADICTS (evidence contradicts the claim), "
            "PARTIALLY_SUPPORTS (related but nuanced/conditional), "
            "INSUFFICIENT_INFO (cannot determine from available text), "
            "or NOT_RELEVANT (off-topic)"
        ),
        pattern=r"^(SUPPORTS|CONTRADICTS|PARTIALLY_SUPPORTS|INSUFFICIENT_INFO|NOT_RELEVANT)$",
    )
    confidence: float = Field(
        ...,
        description="Confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        ...,
        description="Explanation of the assessment with specific evidence from the text",
    )
    suggested_modification: str | None = Field(
        None,
        description=(
            "If the article suggests a modification to the original claim, "
            "provide the revised wording here. Null if no modification needed."
        ),
    )


class ExtractedAbstract(BaseModel):
    """Structured output for abstract extraction."""

    abstract: str | None = Field(
        None,
        description="The extracted abstract text, or null if not found",
    )
    found: bool = Field(
        ...,
        description="Whether an abstract was successfully extracted",
    )


class ExtractedArticleMetadata(BaseModel):
    """Structured output for extracting both abstract and DOI from HTML."""

    abstract: str | None = Field(
        None,
        description="The extracted abstract text, or null if not found",
    )
    abstract_found: bool = Field(
        ...,
        description="Whether an abstract was successfully extracted",
    )
    doi: str | None = Field(
        None,
        description="The DOI of the article (e.g., '10.1038/s41586-021-03819-2'), or null if not found. "
        "Extract only the DOI for THIS article, not DOIs from references.",
    )
    doi_found: bool = Field(
        ...,
        description="Whether the DOI for THIS article was found (not DOIs from references)",
    )
    generated_summary: str | None = Field(
        None,
        description="If no abstract was found, generate a concise summary (2-4 sentences) "
        "including: research question/objective, methods used, and main findings. "
        "This should capture the essence of the paper even without an explicit abstract.",
    )
    used_generated_summary: bool = Field(
        default=False,
        description="Whether the generated summary is being used as the abstract",
    )


class RelevanceScore(BaseModel):
    """Structured output for article relevance scoring."""

    score: float = Field(
        ...,
        description="Relevance score from 0.0 (completely irrelevant) to 1.0 (highly relevant)",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of why this score was given",
    )
    key_matches: list[str] = Field(
        default_factory=list,
        description="Key concepts from the sentence that match this article",
    )


class SentenceContextRewrite(BaseModel):
    """Structured output for sentence context rewriting."""

    rewritten_sentence: str = Field(
        ...,
        description="Self-contained rewrite of the sentence",
    )


class StanceEvaluation(BaseModel):
    """Structured output for detailed stance evaluation."""

    stance: str = Field(
        ...,
        description="Whether the article SUPPORTS, CONTRADICTS, or PARTIALLY_SUPPORTS the sentence",
        pattern=r"^(SUPPORTS|CONTRADICTS|PARTIALLY_SUPPORTS)$",
    )
    confidence: float = Field(
        ...,
        description="Confidence in the stance evaluation (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        ...,
        description="Detailed explanation with specific evidence from the article",
    )
    evidence: str | None = Field(
        None,
        description="Direct quotes or specific findings that support the stance",
    )
    modification: str | None = Field(
        None,
        description="Suggested sentence modification if stance is not SUPPORTS",
    )


class FinalSynthesis(BaseModel):
    """Structured output for final verdict synthesis."""

    verdict: str = Field(
        ...,
        description="Overall verdict: WELL_SUPPORTED, PARTIALLY_SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE, or NOT_SUPPORTED",
        pattern=r"^(WELL_SUPPORTED|PARTIALLY_SUPPORTED|CONTRADICTED|INSUFFICIENT_EVIDENCE|NOT_SUPPORTED)$",
    )
    confidence: float = Field(
        ...,
        description="Overall confidence (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    primary_sources: list[str] = Field(
        default_factory=list,
        description="Titles of the most important sources",
    )
    synthesis: str = Field(
        ...,
        description="Explanation of how the evidence leads to this verdict",
    )
    citation_suggestion: str | None = Field(
        None,
        description="Suggested citation if sentence is supported",
    )
    rewording_suggestion: str | None = Field(
        None,
        description="Suggested rewording if needed",
    )


class LLMClient:
    """Pydantic-ai powered LLM client for RefWeaver with structured output."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        """Initialize the LLM client.

        Args:
            config: LLM configuration. If None, creates from environment.
        """
        self.config = config or LLMConfig()
        self._model_name: str | None = None
        self._provider: OpenAIProvider | None = None
        self._model: OpenAIChatModel | None = None
        self.request_timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        self.request_retries = int(os.getenv("LLM_RETRIES", "3"))

        logger.info(f"LLMClient initialized with base_url: {self.config.base_url}")

    def _get_model_name(self) -> str:
        """Get the model name (lazy loading)."""
        if self._model_name is None:
            self._model_name = self.config.get_model()
        return self._model_name

    def _get_provider(self) -> OpenAIProvider:
        """Get or create the OpenAI provider."""
        if self._provider is None:
            self._provider = OpenAIProvider(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
            )
        return self._provider

    def _get_model(self) -> OpenAIChatModel:
        """Get or create the chat model."""
        if self._model is None:
            self._model = OpenAIChatModel(
                model_name=self._get_model_name(),
                provider=self._get_provider(),
            )
        return self._model

    def _run_agent_sync(self, agent: Any, prompt: str) -> Any:
        return retry_call(
            lambda: run_with_timeout(agent.run_sync, self.request_timeout_seconds, prompt),
            retries=self.request_retries,
        )

    async def _run_agent_async(self, agent: Any, prompt: str) -> Any:
        attempts = self.request_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.wait_for(
                    agent.run(prompt), timeout=self.request_timeout_seconds
                )
            except Exception as exc:
                if attempt >= attempts:
                    raise
                logger.warning(
                    f"Retrying agent run after error: {exc!r} "
                    f"(attempt {attempt}/{self.request_retries})"
                )

    def generate_search_keywords(
        self,
        sentence: str,
    ) -> list[str]:
        """Generate search keywords for finding supporting articles.

        Uses structured output to extract key concepts from a sentence.

        Args:
            sentence: The sentence needing reference support.

        Returns:
            List of search keyword strings.
        """
        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert at constructing academic search queries. "
                "Given a sentence from a scientific manuscript, extract 3-5 keyword phrases "
                "that would find relevant academic articles. Focus on key concepts, "
                "technical terms, methods, and named entities. Avoid generic words."
            ),
            output_type=SearchKeywords,
            output_retries=3,
        )

        prompt = f"Sentence: {sentence}"
        try:
            logger.debug(f"Generating keywords for: {sentence[:60]}...")
            response = self._run_agent_sync(agent, prompt)
            result = cast(SearchKeywords, response.output)
            keywords = result.keywords
            logger.info(f"Generated {len(keywords)} keywords: {keywords}")
            return keywords
        except Exception as e:
            logger.error(f"Keyword generation failed: {e}")
            return [sentence[:100]]  # Fallback

    async def generate_search_keywords_async(
        self,
        sentence: str,
    ) -> list[str]:
        """Async version of generate_search_keywords."""
        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert at constructing academic search queries. "
                "Given a sentence from a scientific manuscript, extract 3-5 keyword phrases "
                "that would find relevant academic articles. Focus on key concepts, "
                "technical terms, methods, and named entities. Avoid generic words."
            ),
            output_type=SearchKeywords,
            output_retries=3,
        )

        prompt = f"Sentence: {sentence}"
        try:
            logger.debug(f"Generating keywords (async) for: {sentence[:60]}...")
            response = await self._run_agent_async(agent, prompt)
            result = cast(SearchKeywords, response.output)
            keywords = result.keywords
            logger.info(f"Generated {len(keywords)} keywords: {keywords}")
            return keywords
        except Exception as e:
            logger.error(f"Keyword generation failed: {e}")
            return [sentence[:100]]  # Fallback

    def analyze_sentence_needs_reference(
        self,
        sentence: str,
        context: str = "",
    ) -> dict[str, bool | str]:
        """Analyze if a sentence needs a reference.

        Args:
            sentence: The sentence to analyze.
            context: Optional surrounding paragraph context.

        Returns:
            Dict with 'needs_reference' (bool) and 'reason' (str).
        """
        context_str = f"\nContext: {context}" if context else ""
        prompt = f"""Analyze this sentence from a scientific manuscript introduction and determine if it needs a reference.

Sentence: {sentence}{context_str}

Guidelines for sentences that NEED references:
- Specific facts, data, or statistics
- Claims about existing research or findings
- Methodology descriptions that aren't novel
- Historical statements about scientific progress
- Comparisons to prior work

Guidelines for sentences that DON'T need references:
- General statements of purpose or scope
- Novel contributions of this paper
- Outline of paper structure
- Well-established facts in the field (common knowledge)"""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert scientific editor reviewing manuscript introductions. "
                "Determine if sentences need citations based on academic writing conventions."
            ),
            output_type=SentenceAnalysis,
            output_retries=3,
        )

        try:
            logger.debug(f"Analyzing sentence: {sentence[:80]}...")
            response = self._run_agent_sync(agent, prompt)
            result = cast(SentenceAnalysis, response.output)
            logger.debug(f"Analysis result: needs_reference={result.needs_reference}")
            return {
                "needs_reference": result.needs_reference,
                "reason": result.reason,
            }
        except Exception as e:
            logger.error(f"Sentence analysis failed: {e}")
            return {
                "needs_reference": False,
                "reason": f"Error: {e}",
            }

    def rewrite_sentence_with_context(
        self,
        sentence: str,
        context: str,
    ) -> str:
        """Rewrite a sentence into a self-contained form using paragraph context.

        Args:
            sentence: The original sentence.
            context: The full paragraph containing the sentence.

        Returns:
            Self-contained sentence string.
        """
        prompt = f"""Rewrite the following sentence so it is self-contained.

Sentence: {sentence}

Paragraph context:
{context}

Instructions:
- Replace pronouns or vague references with explicit subjects from the context.
- Preserve the original meaning and tense.
- Do not add new claims or facts.
- Return only the rewritten sentence."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You rewrite sentences so they are self-contained and unambiguous, "
                "using provided context."
            ),
            output_type=SentenceContextRewrite,
            output_retries=3,
        )

        try:
            logger.debug(f"Rewriting sentence with context: {sentence[:80]}...")
            response = self._run_agent_sync(agent, prompt)
            result = cast(SentenceContextRewrite, response.output)
            rewritten = result.rewritten_sentence.strip()
            return rewritten or sentence
        except Exception as e:
            logger.error(f"Sentence rewrite failed: {e}")
            return sentence

    async def analyze_sentence_needs_reference_async(
        self,
        sentence: str,
        context: str = "",
    ) -> dict[str, bool | str]:
        """Async version of analyze_sentence_needs_reference."""
        context_str = f"\nContext: {context}" if context else ""
        prompt = f"""Analyze this sentence from a scientific manuscript introduction and determine if it needs a reference.

Sentence: {sentence}{context_str}

Guidelines for sentences that NEED references:
- Specific facts, data, or statistics
- Claims about existing research or findings
- Methodology descriptions that aren't novel
- Historical statements about scientific progress
- Comparisons to prior work

Guidelines for sentences that DON'T need references:
- General statements of purpose or scope
- Novel contributions of this paper
- Outline of paper structure
- Well-established facts in the field (common knowledge)"""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert scientific editor reviewing manuscript introductions. "
                "Determine if sentences need citations based on academic writing conventions."
            ),
            output_type=SentenceAnalysis,
            output_retries=3,
        )

        try:
            logger.debug(f"Analyzing sentence (async): {sentence[:80]}...")
            response = await self._run_agent_async(agent, prompt)
            result = cast(SentenceAnalysis, response.output)
            return {
                "needs_reference": result.needs_reference,
                "reason": result.reason,
            }
        except Exception as e:
            logger.error(f"Sentence analysis failed: {e}")
            return {
                "needs_reference": False,
                "reason": f"Error: {e}",
            }

    def evaluate_article_relevance(
        self,
        sentence: str,
        article_title: str,
        article_authors: list[str],
        article_year: int | None,
        article_abstract: str | None,
    ) -> dict[str, str | float | None]:
        """Evaluate if an article is relevant to support a sentence (abstract only).

        This is the first-pass evaluation using only the abstract.
        For a full-text evaluation, use evaluate_article_relevance_fulltext().

        Args:
            sentence: The claim needing support.
            article_title: Title of the article.
            article_authors: List of author names.
            article_year: Publication year (optional).
            article_abstract: Article abstract (optional).

        Returns:
            Dict with 'verdict' (str), 'confidence' (float 0-1),
            'reasoning' (str), and 'suggested_modification' (str | None).
        """
        abstract = article_abstract or "[Abstract not available]"
        authors_str = ", ".join(article_authors[:3])
        if len(article_authors) > 3:
            authors_str += ", et al."
        year_str = str(article_year) if article_year else "Unknown"

        prompt = f"""Evaluate how this article relates to the following claim.

CLAIM TO SUPPORT:
{sentence}

ARTICLE:
Title: {article_title}
Authors: {authors_str}
Year: {year_str}
Abstract: {abstract[:1500]}

INSTRUCTIONS:
Based on the abstract, assess how this article relates to the claim:
- SUPPORTS: Evidence clearly backs the claim
- CONTRADICTS: Evidence contradicts the claim
- PARTIALLY_SUPPORTS: Related but nuanced/conditional
- INSUFFICIENT_INFO: Cannot determine from abstract alone
- NOT_RELEVANT: Off-topic

If the article suggests a modification to the original claim, provide the revised wording."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert scientific reviewer evaluating research articles. "
                "Assess whether articles support, contradict, or relate to specific claims. "
                "Be precise and cite specific evidence from the text."
            ),
            output_type=ArticleRelevance,
            output_retries=3,
        )

        try:
            logger.debug(f"Evaluating article '{article_title[:50]}...' from abstract")
            response = self._run_agent_sync(agent, prompt)
            result = cast(ArticleRelevance, response.output)
            logger.info(
                f"Article evaluation: verdict={result.verdict}, confidence={result.confidence:.2f}"
            )
            return {
                "verdict": result.verdict,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "suggested_modification": result.suggested_modification,
            }
        except Exception as e:
            logger.error(f"Article evaluation failed: {e}")
            return {
                "verdict": "INSUFFICIENT_INFO",
                "confidence": 0.0,
                "reasoning": f"Error during evaluation: {e}",
                "suggested_modification": None,
            }

    async def evaluate_article_relevance_async(
        self,
        sentence: str,
        article_title: str,
        article_authors: list[str],
        article_year: int | None,
        article_abstract: str | None,
    ) -> dict[str, str | float | None]:
        """Async version of evaluate_article_relevance (abstract only)."""
        abstract = article_abstract or "[Abstract not available]"
        authors_str = ", ".join(article_authors[:3])
        if len(article_authors) > 3:
            authors_str += ", et al."
        year_str = str(article_year) if article_year else "Unknown"

        prompt = f"""Evaluate how this article relates to the following claim.

CLAIM TO SUPPORT:
{sentence}

ARTICLE:
Title: {article_title}
Authors: {authors_str}
Year: {year_str}
Abstract: {abstract[:1500]}

INSTRUCTIONS:
Based on the abstract, assess how this article relates to the claim:
- SUPPORTS: Evidence clearly backs the claim
- CONTRADICTS: Evidence contradicts the claim
- PARTIALLY_SUPPORTS: Related but nuanced/conditional
- INSUFFICIENT_INFO: Cannot determine from abstract alone
- NOT_RELEVANT: Off-topic

If the article suggests a modification to the original claim, provide the revised wording."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert scientific reviewer evaluating research articles. "
                "Assess whether articles support, contradict, or relate to specific claims. "
                "Be precise and cite specific evidence from the text."
            ),
            output_type=ArticleRelevance,
            output_retries=3,
        )

        try:
            logger.debug(f"Evaluating article (async) '{article_title[:50]}...' from abstract")
            response = await self._run_agent_async(agent, prompt)
            result = cast(ArticleRelevance, response.output)
            return {
                "verdict": result.verdict,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "suggested_modification": result.suggested_modification,
            }
        except Exception as e:
            logger.error(f"Article evaluation failed: {e}")
            return {
                "verdict": "INSUFFICIENT_INFO",
                "confidence": 0.0,
                "reasoning": f"Error: {e}",
                "suggested_modification": None,
            }

    def evaluate_article_relevance_fulltext(
        self,
        sentence: str,
        article_title: str,
        article_authors: list[str],
        article_year: int | None,
        fulltext_content: str,
    ) -> dict[str, str | float | None]:
        """Evaluate article relevance using full text content.

        This provides a more thorough evaluation when the full PDF is available.
        The fulltext_content should be extracted text from the PDF.

        Args:
            sentence: The claim needing support.
            article_title: Title of the article.
            article_authors: List of author names.
            article_year: Publication year (optional).
            fulltext_content: Extracted text from the full PDF.

        Returns:
            Dict with 'verdict', 'confidence', 'reasoning', 'suggested_modification'.
        """
        authors_str = ", ".join(article_authors[:3])
        if len(article_authors) > 3:
            authors_str += ", et al."
        year_str = str(article_year) if article_year else "Unknown"

        # Limit content length to avoid token limits
        truncated_content = fulltext_content[:20000]

        prompt = f"""Evaluate how this article relates to the following claim using the FULL TEXT.

CLAIM TO SUPPORT:
{sentence}

ARTICLE:
Title: {article_title}
Authors: {authors_str}
Year: {year_str}

FULL TEXT (truncated if very long):
{truncated_content}

INSTRUCTIONS:
Based on the FULL TEXT, provide a thorough assessment:
- SUPPORTS: Evidence clearly backs the claim
- CONTRADICTS: Evidence contradicts the claim
- PARTIALLY_SUPPORTS: Related but nuanced/conditional
- INSUFFICIENT_INFO: Cannot determine from available text
- NOT_RELEVANT: Off-topic

Look for specific data, methodology, results, and conclusions that relate to the claim.
If the article suggests a modification to the original claim, provide the revised wording."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert scientific reviewer with access to full research papers. "
                "Thoroughly analyze the text to determine if it supports, contradicts, or "
                "relates to specific claims. Cite specific sections or data."
            ),
            output_type=ArticleRelevance,
            output_retries=3,
        )

        try:
            logger.debug(f"Evaluating full text of '{article_title[:50]}...'")
            response = self._run_agent_sync(agent, prompt)
            result = cast(ArticleRelevance, response.output)
            logger.info(
                f"Full-text evaluation: verdict={result.verdict}, "
                f"confidence={result.confidence:.2f}"
            )
            return {
                "verdict": result.verdict,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "suggested_modification": result.suggested_modification,
            }
        except Exception as e:
            logger.error(f"Full-text evaluation failed: {e}")
            return {
                "verdict": "INSUFFICIENT_INFO",
                "confidence": 0.0,
                "reasoning": f"Error during evaluation: {e}",
                "suggested_modification": None,
            }

    async def evaluate_article_relevance_fulltext_async(
        self,
        sentence: str,
        article_title: str,
        article_authors: list[str],
        article_year: int | None,
        fulltext_content: str,
    ) -> dict[str, str | float | None]:
        """Async version of evaluate_article_relevance_fulltext."""
        authors_str = ", ".join(article_authors[:3])
        if len(article_authors) > 3:
            authors_str += ", et al."
        year_str = str(article_year) if article_year else "Unknown"

        truncated_content = fulltext_content[:20000]

        prompt = f"""Evaluate how this article relates to the following claim using the FULL TEXT.

CLAIM TO SUPPORT:
{sentence}

ARTICLE:
Title: {article_title}
Authors: {authors_str}
Year: {year_str}

FULL TEXT (truncated if very long):
{truncated_content}

INSTRUCTIONS:
Based on the FULL TEXT, provide a thorough assessment:
- SUPPORTS: Evidence clearly backs the claim
- CONTRADICTS: Evidence contradicts the claim
- PARTIALLY_SUPPORTS: Related but nuanced/conditional
- INSUFFICIENT_INFO: Cannot determine from available text
- NOT_RELEVANT: Off-topic

Look for specific data, methodology, results, and conclusions.
If the article suggests a modification, provide revised wording."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert scientific reviewer with access to full research papers. "
                "Thoroughly analyze the text to determine if it supports, contradicts, or "
                "relates to specific claims. Cite specific sections or data."
            ),
            output_type=ArticleRelevance,
            output_retries=3,
        )

        try:
            logger.debug(f"Evaluating full text (async) of '{article_title[:50]}...'")
            response = await self._run_agent_async(agent, prompt)
            result = cast(ArticleRelevance, response.output)
            return {
                "verdict": result.verdict,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "suggested_modification": result.suggested_modification,
            }
        except Exception as e:
            logger.error(f"Full-text evaluation failed: {e}")
            return {
                "verdict": "INSUFFICIENT_INFO",
                "confidence": 0.0,
                "reasoning": f"Error: {e}",
                "suggested_modification": None,
            }

    def extract_abstract_from_html(
        self,
        html_content: str,
        article_title: str,
    ) -> str | None:
        """Extract abstract from HTML content using LLM.

        Args:
            html_content: Cleaned text content from web page(s).
            article_title: Title of the article for context.

        Returns:
            Extracted abstract text, or None if extraction failed.
        """
        prompt = f"""Extract the abstract from the following web page content.

Article Title: {article_title}

Content:
{html_content[:12000]}

If no abstract is found, set found=false."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are a helpful assistant that extracts abstracts from academic "
                "paper web pages. Return the abstract text if found."
            ),
            output_type=ExtractedAbstract,
            output_retries=3,
        )

        try:
            logger.debug(f"Sending abstract extraction request for: {article_title[:50]}...")
            response = self._run_agent_sync(agent, prompt)
            result = response.output

            if result.found and result.abstract:
                logger.info(
                    f"Successfully extracted abstract ({len(result.abstract)} chars) "
                    f"for: {article_title[:50]}..."
                )
                return str(result.abstract)
            else:
                logger.info(f"No abstract found for: {article_title[:50]}...")
                return None

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None

    async def extract_abstract_from_html_async(
        self,
        html_content: str,
        article_title: str,
    ) -> str | None:
        """Async version of extract_abstract_from_html."""
        prompt = f"""Extract the abstract from the following web page content.

Article Title: {article_title}

Content:
{html_content[:12000]}

If no abstract is found, set found=false."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are a helpful assistant that extracts abstracts from academic "
                "paper web pages. Return the abstract text if found."
            ),
            output_type=ExtractedAbstract,
            output_retries=3,
        )

        try:
            logger.debug(
                f"Sending abstract extraction request (async) for: {article_title[:50]}..."
            )
            response = await self._run_agent_async(agent, prompt)
            result = response.output

            if result.found and result.abstract:
                return str(result.abstract)
            else:
                return None

        except Exception as e:
            logger.error(f"Async LLM extraction failed: {e}")
            return None

    def extract_metadata_from_html(
        self,
        html_content: str,
        article_title: str,
    ) -> dict[str, str | None]:
        """Extract abstract, DOI, and generate summary from HTML content using LLM.

        This method uses structured output to extract both the abstract and DOI
        from academic paper web pages. The LLM is instructed to distinguish
        between the article's own DOI and DOIs found in references.

        If no explicit abstract is found, the LLM generates a concise summary
        including methods and main findings.

        Args:
            html_content: Cleaned text content from web page(s).
            article_title: Title of the article for context.

        Returns:
            Dict with 'abstract' (str | None), 'doi' (str | None).
        """
        prompt = f"""Extract the abstract and DOI from the following web page content.

Article Title: {article_title}

Content:
{html_content[:12000]}

INSTRUCTIONS:
1. Extract the abstract of THIS article (the main content, not from references section)
2. If NO explicit abstract is found, generate a concise summary (2-4 sentences) that includes:
   - The research question or objective
   - The methods used
   - The main findings or conclusions
   Set used_generated_summary=true and put this in generated_summary field
3. Extract the DOI of THIS article only - look for it near the title, in citation info, or metadata
4. IMPORTANT: Do NOT extract DOIs from the references/bibliography section at the end
5. The DOI should start with "10." (e.g., "10.1038/s41586-021-03819-2")
6. Return only the DOI value, not the full URL

If abstract or DOI is not found, set the corresponding found flag to false."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are a helpful assistant that extracts metadata from academic "
                "paper web pages. You can identify the article's own DOI vs DOIs "
                "in the reference list. If no abstract is found, you can generate "
                "a concise summary based on the paper's content."
            ),
            output_type=ExtractedArticleMetadata,
            output_retries=3,
        )

        try:
            logger.debug(f"Sending metadata extraction request for: {article_title[:50]}...")
            response = self._run_agent_sync(agent, prompt)
            result = response.output

            # Determine abstract: use explicit abstract or generated summary
            abstract = None
            if result.abstract_found and result.abstract:
                abstract = result.abstract
            elif result.used_generated_summary and result.generated_summary:
                abstract = result.generated_summary
                logger.info(
                    f"Using generated summary as abstract ({len(abstract)} chars) "
                    f"for: {article_title[:50]}..."
                )

            extracted = {
                "abstract": abstract,
                "doi": result.doi if result.doi_found else None,
            }

            if result.abstract_found and result.abstract:
                logger.info(
                    f"Successfully extracted abstract ({len(result.abstract)} chars) "
                    f"for: {article_title[:50]}..."
                )
            if extracted["doi"]:
                logger.info(
                    f"Successfully extracted DOI ({extracted['doi']}) for: {article_title[:50]}..."
                )

            return extracted

        except Exception as e:
            logger.error(f"LLM metadata extraction failed: {e}")
            return {"abstract": None, "doi": None}

    async def extract_metadata_from_html_async(
        self,
        html_content: str,
        article_title: str,
    ) -> dict[str, str | None]:
        """Async version of extract_metadata_from_html."""
        prompt = f"""Extract the abstract and DOI from the following web page content.

Article Title: {article_title}

Content:
{html_content[:12000]}

INSTRUCTIONS:
1. Extract the abstract of THIS article (the main content, not from references section)
2. If NO explicit abstract is found, generate a concise summary (2-4 sentences) that includes:
   - The research question or objective
   - The methods used
   - The main findings or conclusions
   Set used_generated_summary=true and put this in generated_summary field
3. Extract the DOI of THIS article only - look for it near the title, in citation info, or metadata
4. IMPORTANT: Do NOT extract DOIs from the references/bibliography section at the end
5. The DOI should start with "10." (e.g., "10.1038/s41586-021-03819-2")
6. Return only the DOI value, not the full URL

If abstract or DOI is not found, set the corresponding found flag to false."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are a helpful assistant that extracts metadata from academic "
                "paper web pages. You can identify the article's own DOI vs DOIs "
                "in the reference list. If no abstract is found, you can generate "
                "a concise summary based on the paper's content."
            ),
            output_type=ExtractedArticleMetadata,
            output_retries=3,
        )

        try:
            logger.debug(
                f"Sending metadata extraction request (async) for: {article_title[:50]}..."
            )
            response = await agent.run(prompt)
            result = response.output

            # Determine abstract: use explicit abstract or generated summary
            abstract = None
            if result.abstract_found and result.abstract:
                abstract = result.abstract
            elif result.used_generated_summary and result.generated_summary:
                abstract = result.generated_summary
                logger.info(
                    f"Using generated summary as abstract ({len(abstract)} chars) "
                    f"for: {article_title[:50]}..."
                )

            extracted = {
                "abstract": abstract,
                "doi": result.doi if result.doi_found else None,
            }

            if result.abstract_found and result.abstract:
                logger.info(
                    f"Successfully extracted abstract ({len(result.abstract)} chars) "
                    f"for: {article_title[:50]}..."
                )
            if extracted["doi"]:
                logger.info(
                    f"Successfully extracted DOI ({extracted['doi']}) for: {article_title[:50]}..."
                )

            return extracted

        except Exception as e:
            logger.error(f"Async LLM metadata extraction failed: {e}")
            return {"abstract": None, "doi": None}

    def score_article_relevance(
        self,
        sentence: str,
        article_title: str,
        article_abstract: str | None,
    ) -> dict[str, Any]:
        """Score how relevant an article is to a sentence (Stage 1).

        This is a quick first-pass filter to identify potentially relevant articles
        before doing detailed stance evaluation.

        Args:
            sentence: The claim/sentence to evaluate.
            article_title: Title of the article.
            article_abstract: Article abstract (may be None).

        Returns:
            Dict with 'score' (float 0-1), 'reasoning' (str), 'key_matches' (list).
        """
        abstract = article_abstract or "[No abstract available]"

        prompt = f"""Rate how relevant this article is to the given sentence/claim.

SENTENCE:
{sentence}

ARTICLE:
Title: {article_title}
Abstract: {abstract[:1500]}

INSTRUCTIONS:
1. Score relevance from 0.0 (completely irrelevant) to 1.0 (highly relevant)
2. Consider: Do the main concepts match? Is this the same research area?
3. 0.0-0.3: Different field or off-topic
4. 0.3-0.6: Related field but not directly addressing the claim
5. 0.6-0.8: Relevant to the topic, might provide context
6. 0.8-1.0: Directly addresses the specific claim

Provide your score and brief reasoning."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert research assistant evaluating article relevance. "
                "Be objective and consistent in your scoring. Focus on conceptual overlap."
            ),
            output_type=RelevanceScore,
            output_retries=3,
        )

        try:
            logger.debug(f"Scoring relevance for: {article_title[:50]}...")
            response = self._run_agent_sync(agent, prompt)
            result = response.output

            logger.debug(f"Relevance score: {result.score:.2f} - {article_title[:50]}...")
            return {
                "score": result.score,
                "reasoning": result.reasoning,
                "key_matches": result.key_matches,
            }

        except Exception as e:
            logger.error(f"Relevance scoring failed: {e}")
            return {"score": 0.0, "reasoning": f"Error: {e}", "key_matches": []}

    def evaluate_article_stance(
        self,
        sentence: str,
        article_title: str,
        article_authors: list[str],
        article_year: int | None,
        article_abstract: str | None,
        article_fulltext: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate detailed stance of an article (Stage 2).

        Only call this for articles that passed the relevance threshold.
        Determines if the article supports, contradicts, or partially supports
        the sentence, with detailed reasoning.

        Args:
            sentence: The claim/sentence to evaluate.
            article_title: Title of the article.
            article_authors: List of author names.
            article_year: Publication year.
            article_abstract: Article abstract.
            article_fulltext: Full article text (optional).

        Returns:
            Dict with 'stance', 'confidence', 'reasoning', 'evidence', 'modification'.
        """
        abstract = article_abstract or "[No abstract available]"
        fulltext = article_fulltext or ""
        authors_str = ", ".join(article_authors[:3])
        if len(article_authors) > 3:
            authors_str += ", et al."
        year_str = str(article_year) if article_year else "Unknown"

        if fulltext.strip():
            content_label = "Full text"
            content = fulltext[:20000]
        else:
            content_label = "Abstract"
            content = abstract[:1500]

        prompt = f"""Evaluate how this article relates to the given sentence/claim.

SENTENCE TO EVALUATE:
{sentence}

ARTICLE:
Title: {article_title}
Authors: {authors_str}
Year: {year_str}
{content_label}: {content}

INSTRUCTIONS:
1. Determine if the article SUPPORTS, CONTRADICTS, or PARTIALLY_SUPPORTS the sentence
2. SUPPORTS: Evidence clearly backs the claim
3. CONTRADICTS: Evidence clearly contradicts the claim
4. PARTIALLY_SUPPORTS: Related but with important nuances or conditions
5. Provide specific evidence from the provided text
6. If not SUPPORTS, suggest how the sentence should be modified

Be thorough and cite specific evidence."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert scientific reviewer. Carefully evaluate whether "
                "articles support, contradict, or partially support specific claims. "
                "Always cite specific evidence and be precise about your reasoning."
            ),
            output_type=StanceEvaluation,
            output_retries=3,
        )

        try:
            logger.debug(f"Evaluating stance for: {article_title[:50]}...")
            response = agent.run_sync(prompt)
            result = response.output

            logger.info(
                f"Stance evaluation: {result.stance} (conf: {result.confidence:.2f}) "
                f"for {article_title[:50]}..."
            )
            return {
                "stance": result.stance,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "evidence": result.evidence,
                "modification": result.modification,
            }

        except Exception as e:
            logger.error(f"Stance evaluation failed: {e}")
            return {
                "stance": "PARTIALLY_SUPPORTS",
                "confidence": 0.0,
                "reasoning": f"Error: {e}",
                "evidence": None,
                "modification": None,
            }

    def synthesize_final_verdict(
        self,
        sentence: str,
        evaluations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Synthesize final verdict from all article evaluations (Stage 3).

        Takes all the relevant article evaluations and produces an overall
        assessment of whether the sentence is well-supported by the literature.

        Args:
            sentence: The original sentence/claim.
            evaluations: List of evaluation dicts with 'title', 'stance',
                        'confidence', 'reasoning', etc.

        Returns:
            Dict with final 'verdict', 'confidence', 'primary_sources',
            'synthesis', 'citation_suggestion', 'rewording_suggestion'.
        """
        # Format evaluations for the prompt
        eval_texts = []
        for i, ev in enumerate(evaluations, 1):
            lines = [
                f"Article {i}: {ev.get('title', 'Unknown')}",
                f"  Stance: {ev.get('stance', 'UNKNOWN')} (confidence: {ev.get('confidence', 0):.2f})",
                f"  Reasoning: {ev.get('reasoning', 'N/A')[:300]}...",
            ]
            if ev.get("evidence"):
                lines.append(f"  Evidence: {ev['evidence'][:200]}...")
            eval_texts.append("\n".join(lines))

        evaluations_str = "\n\n".join(eval_texts)

        prompt = f"""Synthesize a final verdict for this sentence based on all article evaluations.

SENTENCE:
{sentence}

ARTICLE EVALUATIONS:
{evaluations_str}

INSTRUCTIONS:
1. Consider all the evidence from the evaluated articles
2. Determine overall verdict:
   - WELL_SUPPORTED: Strong evidence supports the claim
   - PARTIALLY_SUPPORTED: Some support but with caveats
   - CONTRADICTED: Evidence contradicts the claim
   - INSUFFICIENT_EVIDENCE: Not enough relevant articles found
   - NOT_SUPPORTED: No supporting evidence found
3. Identify the primary sources (most relevant, highest confidence)
4. Explain how the evidence leads to your verdict
5. Suggest citation format if supported, or rewording if needed

Provide a balanced assessment based on the weight of evidence."""

        agent = Agent(
            model=self._get_model(),
            system_prompt=(
                "You are an expert research synthesizer. Carefully weigh all the "
                "evidence to provide a well-reasoned final verdict. Be objective "
                "and acknowledge limitations in the available evidence."
            ),
            output_type=FinalSynthesis,
            output_retries=3,
        )

        try:
            logger.debug(f"Synthesizing final verdict for: {sentence[:60]}...")
            response = agent.run_sync(prompt)
            result = response.output

            logger.success(f"Final verdict: {result.verdict} (confidence: {result.confidence:.2f})")
            return {
                "verdict": result.verdict,
                "confidence": result.confidence,
                "primary_sources": result.primary_sources,
                "synthesis": result.synthesis,
                "citation_suggestion": result.citation_suggestion,
                "rewording_suggestion": result.rewording_suggestion,
            }

        except Exception as e:
            logger.error(f"Final synthesis failed: {e}")
            return {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "confidence": 0.0,
                "primary_sources": [],
                "synthesis": f"Error during synthesis: {e}",
                "citation_suggestion": None,
                "rewording_suggestion": None,
            }
