"""Adapter classes for academic search APIs."""

from refweaver.adapters.openalex import OpenAlexAdapter
from refweaver.adapters.scholarly import GoogleScholarAdapter
from refweaver.adapters.semantic_scholar import SemanticScholarAdapter

__all__ = ["GoogleScholarAdapter", "OpenAlexAdapter", "SemanticScholarAdapter"]
