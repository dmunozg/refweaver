"""LLM client configuration and utilities for RefWeaver.

Supports OpenAI-compatible APIs (vLLM, OpenAI, etc.) with configuration
via environment variables for containerized deployment.
"""

import os
from typing import Optional

import requests
from loguru import logger
from openai import AsyncOpenAI, OpenAI


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
            return self.model

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch models from {self.base_url}: {e}")
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format from /models endpoint: {e}")


class LLMClient:
    """OpenAI-compatible LLM client for RefWeaver."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        """Initialize the LLM client.

        Args:
            config: LLM configuration. If None, creates from environment.
        """
        self.config = config or LLMConfig()
        self._model: Optional[str] = None

        # Initialize OpenAI client
        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
        )
        self.async_client = AsyncOpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
        )

        logger.info(f"LLMClient initialized with base_url: {self.config.base_url}")

    @property
    def model(self) -> str:
        """Get the model name (lazy loading)."""
        if self._model is None:
            self._model = self.config.get_model()
        return self._model

    def extract_abstract_from_html(
        self,
        html_content: str,
        article_title: str,
    ) -> Optional[str]:
        """Extract abstract from HTML content using LLM.

        Args:
            html_content: Cleaned text content from web page(s).
            article_title: Title of the article for context.

        Returns:
            Extracted abstract text, or None if extraction failed.
        """
        prompt = f"""Extract the abstract from the following web page content.

Article Title: {article_title}

Instructions:
1. Look for sections labeled "Abstract", "Summary", or similar
2. Return ONLY the abstract text, no headers or extra text
3. If no abstract is found, respond with exactly: NO_ABSTRACT_FOUND
4. Clean up any extra whitespace or formatting

Content:
{html_content[:12000]}

Abstract:"""

        try:
            logger.debug(f"Sending abstract extraction request for: {article_title[:50]}...")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts abstracts from academic paper web pages. Return only the abstract text."
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            result = response.choices[0].message.content
            if result and result.strip():
                result = result.strip()
                if result == "NO_ABSTRACT_FOUND":
                    logger.info(f"LLM reported no abstract found for: {article_title[:50]}...")
                    return None
                logger.info(f"Successfully extracted abstract ({len(result)} chars) for: {article_title[:50]}...")
                return result

            return None

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None

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
- Well-established facts in the field (common knowledge)

Respond in this exact format:
NEEDS_REFERENCE: [YES/NO]
REASON: [Brief explanation]
"""

        try:
            logger.debug(f"Analyzing sentence: {sentence[:80]}...")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert scientific editor reviewing manuscript introductions."
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=512,
                temperature=0.0,  # Deterministic for consistency
            )

            result = response.choices[0].message.content
            if not result:
                return {"needs_reference": False, "reason": "LLM returned empty response"}

            # Parse response
            needs_ref = "YES" in result.upper() and "NEEDS_REFERENCE: YES" in result.upper()
            reason = result.split("REASON:")[-1].strip() if "REASON:" in result else result.strip()

            return {
                "needs_reference": needs_ref,
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Sentence analysis failed: {e}")
            return {
                "needs_reference": False,
                "reason": f"Error: {e}",
            }

    async def extract_abstract_async(
        self,
        html_content: str,
        article_title: str,
    ) -> Optional[str]:
        """Async version of extract_abstract_from_html."""
        prompt = f"""Extract the abstract from the following web page content.

Article Title: {article_title}

Instructions:
1. Look for sections labeled "Abstract", "Summary", or similar
2. Return ONLY the abstract text, no headers or extra text
3. If no abstract is found, respond with exactly: NO_ABSTRACT_FOUND
4. Clean up any extra whitespace or formatting

Content:
{html_content[:12000]}

Abstract:"""

        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts abstracts from academic paper web pages. Return only the abstract text."
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            result = response.choices[0].message.content
            if result and result.strip():
                result = result.strip()
                if result == "NO_ABSTRACT_FOUND":
                    return None
                return result

            return None

        except Exception as e:
            logger.error(f"Async LLM extraction failed: {e}")
            return None
