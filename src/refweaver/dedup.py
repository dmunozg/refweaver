"""Utilities for deduplicating articles from multiple sources."""

import re

from pydantic import HttpUrl

from refweaver.models import Article


def normalize_title(title: str) -> str:
    """Normalize a title for comparison.

    Removes punctuation, extra whitespace, and converts to lowercase.
    """
    # Convert to lowercase
    normalized = title.lower()
    # Remove common punctuation and special chars
    normalized = re.sub(r'[^\w\s]', '', normalized)
    # Normalize whitespace
    normalized = ' '.join(normalized.split())
    return normalized


def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two titles (0.0 to 1.0).

    Uses a simple word overlap ratio for now.
    Could be enhanced with Levenshtein distance if needed.
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    if norm1 == norm2:
        return 1.0

    words1: set[str] = set(norm1.split())
    words2: set[str] = set(norm2.split())

    if not words1 or not words2:
        return 0.0

    # Jaccard similarity
    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)


def author_overlap(authors1: list[str], authors2: list[str]) -> float:
    """Calculate the overlap ratio between two author lists.

    Returns 0.0 to 1.0 based on shared authors.
    """
    if not authors1 or not authors2:
        return 0.0

    # Normalize author names for comparison
    def normalize_author(name: str) -> str:
        # Lowercase and remove extra whitespace
        return ' '.join(name.lower().split())

    set1: set[str] = {normalize_author(a) for a in authors1}
    set2: set[str] = {normalize_author(a) for a in authors2}

    intersection = set1 & set2
    smaller_set_size = min(len(set1), len(set2))

    if smaller_set_size == 0:
        return 0.0

    return len(intersection) / smaller_set_size


def are_articles_duplicate(
    article1: Article,
    article2: Article,
    title_threshold: float = 0.85,
    author_threshold: float = 0.5,
) -> bool:
    """Check if two articles are likely duplicates.

    Comparison priority:
    1. DOI match (exact, if both have DOIs)
    2. External ID match (same article from same source)
    3. Title similarity + author overlap + year match

    Args:
        article1: First article to compare
        article2: Second article to compare
        title_threshold: Minimum title similarity (0.0-1.0) to consider match
        author_threshold: Minimum author overlap (0.0-1.0) to consider match

    Returns:
        True if articles are likely the same, False otherwise
    """
    # Same source and same external ID = definitely same article
    if (article1.source == article2.source and
        article1.external_id == article2.external_id):
        return True

    # DOI match (the gold standard)
    if article1.doi and article2.doi:
        # Normalize DOIs (remove https://doi.org/ prefix if present)
        doi1 = article1.doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        doi2 = article2.doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        if doi1.lower() == doi2.lower():
            return True

    # If years don't match, they're probably not the same article
    if (
        article1.year is not None
        and article2.year is not None
        and article1.year != article2.year
    ):
        return False

    # Check title similarity
    title_sim = title_similarity(article1.title, article2.title)
    if title_sim < title_threshold:
        return False

    # Check author overlap
    author_sim = author_overlap(article1.authors, article2.authors)
    # Return True if titles are similar, authors overlap, and years match
    return author_sim >= author_threshold


def deduplicate_articles(
    articles: list[Article],
    title_threshold: float = 0.85,
    author_threshold: float = 0.5,
) -> list[Article]:
    """Remove duplicate articles from a list.

    Keeps the first occurrence of each article. Prefers articles with
    more complete metadata (especially DOI).

    Args:
        articles: List of articles potentially containing duplicates
        title_threshold: Minimum title similarity for duplicate detection
        author_threshold: Minimum author overlap for duplicate detection

    Returns:
        List of unique articles
    """
    if not articles:
        return []

    unique_articles: list[Article] = []

    for article in articles:
        is_duplicate = False

        for existing in unique_articles:
            if are_articles_duplicate(
                article,
                existing,
                title_threshold=title_threshold,
                author_threshold=author_threshold,
            ):
                is_duplicate = True
                # Prefer the article with more metadata (especially DOI)
                if article.doi and not existing.doi:
                    # Replace the existing one with this one
                    unique_articles[unique_articles.index(existing)] = article
                break

        if not is_duplicate:
            unique_articles.append(article)

    return unique_articles


def merge_articles(articles: list[Article]) -> Article | None:
    """Merge multiple articles representing the same paper into one.

    Combines metadata from all sources, preferring non-null values.
    Useful when you have the same paper from multiple APIs and want
    the most complete metadata.

    Args:
        articles: List of articles representing the same paper

    Returns:
        Merged article with combined metadata, or None if list is empty
    """
    if not articles:
        return None

    if len(articles) == 1:
        return articles[0]

    base = articles[0]

    # Helper to get first non-null value
    def pick(*values: str | None) -> str | None:
        for v in values:
            if v is not None and v != "":
                return v
        return None

    # Collect all authors (union)
    all_authors: set[str] = set()
    for article in articles:
        all_authors.update(article.authors)

    # Find best DOI
    doi = pick(*[a.doi for a in articles])

    # Find best PDF URL (prefer open access)
    pdf_url = None
    for article in articles:
        if article.pdf_url:
            pdf_url = article.pdf_url
            if article.open_access:
                break  # Prefer open access PDFs

    # Build merged article
    from datetime import date

    # Find best URL
    url_str = pick(*[str(a.url) if a.url else None for a in articles])
    url: HttpUrl | None = None
    if url_str:
        try:
            url = HttpUrl(url_str)
        except Exception:
            url = None

    return Article(
        source=f"merged:{','.join(a.source for a in articles)}",
        external_id=base.external_id,
        title=base.title,
        authors=list(all_authors) if all_authors else base.authors,
        year=base.year,
        journal=pick(*[a.journal for a in articles]),
        publication_type=base.publication_type,
        volume=pick(*[a.volume for a in articles]),
        issue=pick(*[a.issue for a in articles]),
        pages=pick(*[a.pages for a in articles]),
        doi=doi,
        abstract=pick(*[a.abstract for a in articles]),
        url=url,
        pdf_url=pdf_url,
        open_access=any(a.open_access for a in articles),
        citation_count=max(
            (a.citation_count for a in articles if a.citation_count is not None),
            default=None
        ),
        retrieved_at=date.today(),
    )
