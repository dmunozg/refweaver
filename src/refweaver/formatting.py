"""Table formatting utilities for RefWeaver models.

Provides convenient ways to display lists of Pydantic models as tables
in Jupyter notebooks or terminal output.
"""

from typing import Any

from loguru import logger


def articles_to_table(
    articles: list[Any],
    columns: list[str] | None = None,
    max_title_length: int = 60,
) -> str:
    """Convert a list of Article objects to a formatted table string.

    Args:
        articles: List of Article objects.
        columns: Column names to display. Defaults to common fields.
        max_title_length: Truncate titles longer than this.

    Returns:
        Formatted table string (uses tabulate if available, else simple format).
    """
    if not articles:
        return "No articles to display."

    if columns is None:
        columns = ["title", "authors", "year", "doi", "open_access"]

    # Extract data
    rows = []
    for article in articles:
        row = {}
        for col in columns:
            value = getattr(article, col, None)
            if col == "title" and value:
                title = str(value)
                if len(title) > max_title_length:
                    title = title[:max_title_length - 3] + "..."
                row[col] = title
            elif col == "authors" and value:
                authors = value if isinstance(value, list) else [value]
                if len(authors) > 2:
                    row[col] = f"{authors[0]} et al."
                else:
                    row[col] = ", ".join(authors)
            elif col == "doi":
                row[col] = value if value else "-"
            elif col == "open_access":
                row[col] = "✓" if value else ""
            else:
                row[col] = value if value is not None else "-"
        rows.append(row)

    # Try tabulate for nice formatting
    try:
        from tabulate import tabulate  # type: ignore[import-untyped]

        headers = [col.replace("_", " ").title() for col in columns]
        table_data = [[row.get(col, "-") for col in columns] for row in rows]
        result: str = tabulate(table_data, headers=headers, tablefmt="simple")
        return result
    except ImportError:
        # Fallback to simple formatting
        logger.debug("tabulate not installed, using simple formatting")
        return _simple_table_format(rows, columns)


def _simple_table_format(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """Simple table formatting without external dependencies."""
    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val_str = str(row.get(col, "-"))
            widths[col] = max(widths[col], len(val_str))

    # Build table
    lines = []

    # Header
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    lines.append(header)
    lines.append("-" * len(header))

    # Rows
    for row in rows:
        line = " | ".join(
            str(row.get(col, "-")).ljust(widths[col]) for col in columns
        )
        lines.append(line)

    return "\n".join(lines)


def articles_to_pandas(articles: list[Any]) -> Any:
    """Convert a list of Article objects to a pandas DataFrame.

    Args:
        articles: List of Article objects.

    Returns:
        pandas DataFrame (requires pandas to be installed).

    Raises:
        ImportError: If pandas is not installed.
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "pandas is required for articles_to_pandas. "
            "Install with: pip install pandas"
        ) from e

    if not articles:
        return pd.DataFrame()

    # Convert to dicts
    data = []
    for article in articles:
        article_dict = article.model_dump()
        # Truncate long fields
        if article_dict.get("title"):
            title = article_dict["title"]
            if len(title) > 100:
                article_dict["title"] = title[:97] + "..."
        # Format authors
        if article_dict.get("authors"):
            authors = article_dict["authors"]
            if len(authors) > 3:
                article_dict["authors"] = f"{authors[0]} et al. ({len(authors)} authors)"
            else:
                article_dict["authors"] = ", ".join(authors)
        data.append(article_dict)

    df = pd.DataFrame(data)

    # Select and reorder useful columns
    preferred_cols = [
        "title", "authors", "year", "journal", "doi",
        "open_access", "citation_count", "source"
    ]
    available_cols = [c for c in preferred_cols if c in df.columns]
    other_cols = [c for c in df.columns if c not in preferred_cols]
    return df[available_cols + other_cols]


def evaluations_to_table(evaluations: list[Any]) -> str:
    """Convert a list of SentenceEvaluation objects to a table.

    Args:
        evaluations: List of SentenceEvaluation objects.

    Returns:
        Formatted table string.
    """
    if not evaluations:
        return "No evaluations to display."

    rows = []
    for ev in evaluations:
        rows.append({
            "article": ev.article_title[:50] + "..." if len(ev.article_title) > 50 else ev.article_title,
            "relevance": f"{ev.relevance_score:.2f}",
            "stance": ev.stance or "-",
            "stance_conf": f"{ev.stance_confidence:.2f}" if ev.stance_confidence else "-",
            "combined": f"{ev.combined_score:.2f}",
        })

    try:
        from tabulate import tabulate

        result: str = tabulate(
            rows,
            headers="keys",
            tablefmt="simple",
            showindex=False,
        )
        return result
    except ImportError:
        return _simple_table_format(rows, list(rows[0].keys()))
