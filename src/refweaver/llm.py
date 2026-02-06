"""LLM client configuration and utilities for RefWeaver using pydantic-ai.

Supports OpenAI-compatible APIs (vLLM, OpenAI, etc.) with structured output
via Pydantic models.
"""

import os

import requests
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


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

    def generate_search_keywords(self, sentence: str) -> list[str]:
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

        try:
            logger.debug(f"Generating keywords for: {sentence[:60]}...")
            response = agent.run_sync(sentence)
            keywords = response.output.keywords
            logger.info(f"Generated {len(keywords)} keywords: {keywords}")
            return keywords
        except Exception as e:
            logger.error(f"Keyword generation failed: {e}")
            return [sentence[:100]]  # Fallback

    async def generate_search_keywords_async(self, sentence: str) -> list[str]:
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

        try:
            logger.debug(f"Generating keywords (async) for: {sentence[:60]}...")
            response = await agent.run(sentence)
            keywords = response.output.keywords
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
            response = agent.run_sync(prompt)
            result = response.output
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
            response = await agent.run(prompt)
            result = response.output
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
            response = agent.run_sync(prompt)
            result = response.output
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
            logger.debug(
                f"Evaluating article (async) '{article_title[:50]}...' from abstract"
            )
            response = await agent.run(prompt)
            result = response.output
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
            response = agent.run_sync(prompt)
            result = response.output
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
            response = await agent.run(prompt)
            result = response.output
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
            response = agent.run_sync(prompt)
            result = response.output

            if result.found and result.abstract:
                logger.info(
                    f"Successfully extracted abstract ({len(result.abstract)} chars) "
                    f"for: {article_title[:50]}..."
                )
                return result.abstract
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
            response = await agent.run(prompt)
            result = response.output

            if result.found and result.abstract:
                return result.abstract
            else:
                return None

        except Exception as e:
            logger.error(f"Async LLM extraction failed: {e}")
            return None
