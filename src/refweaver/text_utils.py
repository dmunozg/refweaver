"""Text processing utilities for RefWeaver.

Provides functions for splitting manuscripts into paragraphs and sentences,
as well as other text preprocessing utilities.
"""

import re
from typing import List

try:
    from nltk.tokenize import sent_tokenize  # type: ignore[import-untyped]

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


def split_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs based on blank lines.

    Args:
        text: Raw text input, potentially with multiple paragraphs
              separated by blank lines.

    Returns:
        List of non-empty paragraph strings with normalized whitespace.

    Example:
        >>> text = "First paragraph.\\n\\nSecond paragraph.\\n\\n\\nThird."
        >>> split_paragraphs(text)
        ['First paragraph.', 'Second paragraph.', 'Third.']
    """
    # Split on 2+ newlines (with optional whitespace between)
    paragraphs = re.split(r"\n\s*\n", text.strip())
    # Clean and filter empty paragraphs
    return [p.strip() for p in paragraphs if p.strip()]


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK's Punkt tokenizer.

    Requires NLTK to be installed and the 'punkt' data downloaded.
    Automatically downloads the data if not present.

    Args:
        text: Text to split into sentences.

    Returns:
        List of sentence strings.

    Raises:
        ImportError: If NLTK is not installed.

    Example:
        >>> text = "Dr. Smith visited the U.S.A. yesterday. It was sunny."
        >>> split_sentences(text)
        ['Dr. Smith visited the U.S.A. yesterday.', 'It was sunny.']
    """
    if not NLTK_AVAILABLE:
        msg = (
            "NLTK is required for sentence tokenization. "
            "Install with: uv add nltk"
        )
        raise ImportError(msg)

    # Ensure punkt tokenizer is available
    import nltk  # type: ignore[import-untyped]

    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)

    sentences: list[str] = sent_tokenize(text)
    return sentences


def preprocess_manuscript(text: str) -> List[List[str]]:
    """Split a manuscript into paragraphs, then each paragraph into sentences.

    This is the main entry point for processing manuscript text.

    Args:
        text: Full manuscript text.

    Returns:
        List of paragraphs, where each paragraph is a list of sentences.

    Example:
        >>> text = "Para one. Sentence two.\\n\\nPara two."
        >>> preprocess_manuscript(text)
        [['Para one.', 'Sentence two.'], ['Para two.']]
    """
    paragraphs = split_paragraphs(text)
    return [split_sentences(para) for para in paragraphs]
