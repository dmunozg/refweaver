"""Tests for LLM client with pydantic-ai structured output."""

import pytest
from _pytest.monkeypatch import MonkeyPatch

from refweaver.llm import (
    ArticleRelevance,
    ExtractedAbstract,
    LLMClient,
    LLMConfig,
    SearchKeywords,
    SentenceAnalysis,
)


class TestLLMConfig:
    """Test suite for LLM configuration."""

    def test_default_config(self, monkeypatch: MonkeyPatch):
        """Test default configuration values."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        config = LLMConfig()
        assert config.base_url == "http://127.0.0.1:11435/v1"
        assert config.api_key == "not-needed"
        assert config.max_tokens == 4096
        assert config.temperature == 0.1

    def test_custom_config_from_env(self, monkeypatch: MonkeyPatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("OPENAI_BASE_URL", "http://custom:8080/v1")
        monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
        monkeypatch.setenv("LLM_MODEL", "custom-model")
        monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.5")

        config = LLMConfig()
        assert config.base_url == "http://custom:8080/v1"
        assert config.api_key == "secret-key"
        assert config.model == "custom-model"
        assert config.max_tokens == 2048
        assert config.temperature == 0.5


class TestLLMClient:
    """Test suite for LLMClient with pydantic-ai."""

    def test_client_initialization(self):
        """Test LLMClient initializes correctly."""
        client = LLMClient()
        assert client.config is not None

    def test_client_with_custom_config(self):
        """Test LLMClient with custom config."""
        config = LLMConfig()
        config.model = "test-model"
        client = LLMClient(config=config)
        assert client.config.model == "test-model"


class TestOutputModels:
    """Test suite for pydantic output models."""

    def test_search_keywords_model(self):
        """Test SearchKeywords output model."""
        keywords = SearchKeywords(
            keywords=["enzyme stabilization", "nanoparticle hybrid", "protein folding"]
        )
        assert len(keywords.keywords) == 3
        assert "enzyme stabilization" in keywords.keywords

    def test_sentence_analysis_model(self):
        """Test SentenceAnalysis output model."""
        analysis = SentenceAnalysis(
            needs_reference=True,
            reason="Specific statistical claim requiring citation",
        )
        assert analysis.needs_reference is True
        assert "statistical" in analysis.reason

    def test_article_relevance_model(self):
        """Test ArticleRelevance output model."""
        relevance = ArticleRelevance(
            verdict="SUPPORTS",
            confidence=0.85,
            reasoning="Directly supports the claim with experimental evidence",
        )
        assert relevance.verdict == "SUPPORTS"
        assert relevance.confidence == 0.85
        assert 0.0 <= relevance.confidence <= 1.0
        assert relevance.suggested_modification is None

    def test_article_relevance_with_modification(self):
        """Test ArticleRelevance with suggested modification."""
        relevance = ArticleRelevance(
            verdict="PARTIALLY_SUPPORTS",
            confidence=0.70,
            reasoning="The article supports the claim but only at lower temperatures.",
            suggested_modification="Gold nanoparticles stabilize enzymes at temperatures below 40°C.",
        )
        assert relevance.verdict == "PARTIALLY_SUPPORTS"
        assert relevance.suggested_modification is not None
        assert "below 40°C" in relevance.suggested_modification

    def test_extracted_abstract_model(self):
        """Test ExtractedAbstract output model."""
        extraction = ExtractedAbstract(
            abstract="This is the extracted abstract text.",
            found=True,
        )
        assert extraction.found is True
        assert extraction.abstract == "This is the extracted abstract text."

    def test_article_relevance_confidence_validation(self):
        """Test confidence value validation."""
        # Should raise validation error for out-of-range confidence
        with pytest.raises(ValueError):  # pydantic.ValidationError
            ArticleRelevance(
                verdict="SUPPORTS",
                confidence=1.5,  # Out of range
                reasoning="Test",
            )

    def test_search_keywords_min_max_items(self):
        """Test SearchKeywords min/max validation."""
        # Empty list should fail
        with pytest.raises(ValueError):
            SearchKeywords(keywords=[])

        # More than 5 items should fail
        with pytest.raises(ValueError):
            SearchKeywords(keywords=["a", "b", "c", "d", "e", "f"])
