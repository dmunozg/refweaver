"""Tests for abstract enrichment fallback sequencing."""

import sys
import types


class _Logger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


# Minimal stubs for optional third-party deps used at import time.
loguru_stub = types.ModuleType("loguru")
loguru_stub.logger = _Logger()
sys.modules.setdefault("loguru", loguru_stub)

pyalex_stub = types.ModuleType("pyalex")
pyalex_stub.Works = object
pyalex_stub.config = types.SimpleNamespace(email=None)
sys.modules.setdefault("pyalex", pyalex_stub)

scholarly_stub = types.ModuleType("scholarly")
scholarly_stub.ProxyGenerator = object
scholarly_stub.scholarly = types.SimpleNamespace(use_proxy=lambda *_args, **_kwargs: None)
sys.modules.setdefault("scholarly", scholarly_stub)

semanticscholar_stub = types.ModuleType("semanticscholar")
semanticscholar_stub.SemanticScholar = object
sys.modules.setdefault("semanticscholar", semanticscholar_stub)

from refweaver.enrich import ArticleEnricher
from refweaver.models import Article


def _make_article(*, doi: str | None = None, abstract: str | None = None) -> Article:
    return Article(
        source="openalex",
        external_id="W1",
        title="A test article title",
        authors=["Author One"],
        doi=doi,
        abstract=abstract,
    )


def _make_enricher() -> ArticleEnricher:
    enricher = ArticleEnricher.__new__(ArticleEnricher)
    enricher.use_llm_extractor = False
    return enricher


def test_fill_abstract_retries_doi_strategies_after_title_finds_doi_cross_api():
    enricher = _make_enricher()
    article = _make_article()

    calls = {"cross_api": 0, "crossref": 0}

    enricher._fill_from_same_source = lambda a: a

    def cross_api(a: Article) -> Article:
        calls["cross_api"] += 1
        if calls["cross_api"] == 1:
            return a
        return a.model_copy(update={"abstract": "Filled by cross-api"})

    def crossref(a: Article) -> Article:
        calls["crossref"] += 1
        return a

    enricher._fill_from_cross_api = cross_api
    enricher.enrich_from_crossref = crossref
    enricher.enrich_from_pdf_doi = lambda a: a
    enricher._extract_with_llm = lambda a: a
    enricher.enrich_from_title = lambda a: a.model_copy(update={"doi": "10.1000/test"})

    result = enricher.fill_abstract(article)

    assert result.abstract == "Filled by cross-api"
    assert calls["cross_api"] == 2
    assert calls["crossref"] == 0


def test_fill_abstract_retries_doi_strategies_after_title_finds_doi_crossref():
    enricher = _make_enricher()
    article = _make_article()

    calls = {"cross_api": 0, "crossref": 0}

    enricher._fill_from_same_source = lambda a: a

    def cross_api(a: Article) -> Article:
        calls["cross_api"] += 1
        return a

    def crossref(a: Article) -> Article:
        calls["crossref"] += 1
        if calls["crossref"] == 1:
            return a
        return a.model_copy(update={"abstract": "Filled by crossref"})

    enricher._fill_from_cross_api = cross_api
    enricher.enrich_from_crossref = crossref
    enricher.enrich_from_pdf_doi = lambda a: a
    enricher._extract_with_llm = lambda a: a
    enricher.enrich_from_title = lambda a: a.model_copy(update={"doi": "10.1000/test"})

    result = enricher.fill_abstract(article)

    assert result.abstract == "Filled by crossref"
    assert calls["cross_api"] == 2
    assert calls["crossref"] == 2


def test_fill_abstract_doi_already_present_skips_title_search():
    enricher = _make_enricher()
    article = _make_article(doi="10.1000/existing")

    called_title = False

    enricher._fill_from_same_source = lambda a: a
    enricher._fill_from_cross_api = lambda a: a
    enricher.enrich_from_crossref = lambda a: a
    enricher.enrich_from_pdf_doi = lambda a: a
    enricher._extract_with_llm = lambda a: a

    def title_search(a: Article) -> Article:
        nonlocal called_title
        called_title = True
        return a

    enricher.enrich_from_title = title_search

    enricher.fill_abstract(article)

    assert called_title is False


def test_fill_abstract_title_search_failure_does_not_rerun_doi_strategies():
    enricher = _make_enricher()
    article = _make_article()

    calls = {"cross_api": 0, "crossref": 0}

    enricher._fill_from_same_source = lambda a: a

    def cross_api(a: Article) -> Article:
        calls["cross_api"] += 1
        return a

    def crossref(a: Article) -> Article:
        calls["crossref"] += 1
        return a

    enricher._fill_from_cross_api = cross_api
    enricher.enrich_from_crossref = crossref
    enricher.enrich_from_pdf_doi = lambda a: a
    enricher._extract_with_llm = lambda a: a
    enricher.enrich_from_title = lambda a: a

    enricher.fill_abstract(article)

    assert calls["cross_api"] == 1
    assert calls["crossref"] == 0
