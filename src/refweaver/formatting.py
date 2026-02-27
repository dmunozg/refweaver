"""Table formatting utilities for RefWeaver models.

Provides convenient ways to display lists of Pydantic models as tables
in Jupyter notebooks or terminal output.
"""

import hashlib
import json
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from refweaver.evaluation_models import SentenceEvaluation


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
                    title = title[: max_title_length - 3] + "..."
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
        line = " | ".join(str(row.get(col, "-")).ljust(widths[col]) for col in columns)
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
            "pandas is required for articles_to_pandas. Install with: pip install pandas"
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
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "open_access",
        "citation_count",
        "source",
    ]
    available_cols = [c for c in preferred_cols if c in df.columns]
    other_cols = [c for c in df.columns if c not in preferred_cols]
    return df[available_cols + other_cols]


def evaluations_to_table(evaluations: list["SentenceEvaluation"]) -> str:
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
        rows.append(
            {
                "article": ev.article_title[:50] + "..."
                if len(ev.article_title) > 50
                else ev.article_title,
                "relevance": f"{ev.relevance_score:.2f}",
                "stance": ev.stance or "-",
                "stance_conf": f"{ev.stance_confidence:.2f}" if ev.stance_confidence else "-",
                "combined": f"{ev.combined_score:.2f}",
            }
        )

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


def sentence_evaluations_to_markdown(
    results: list[tuple[Any, Any, list[Any]]],
) -> str:
    """Render sentence evaluations into a Markdown report.

    Args:
        results: List of (Sentence, FinalVerdict, list[SentenceEvaluation]).

    Returns:
        Markdown report string.
    """
    lines: list[str] = ["# Reference Analysis Report", ""]

    for index, (sentence, verdict, evaluations) in enumerate(results, start=1):
        lines.append(f"## Sentence {index}")
        lines.append("")
        lines.append(f"**Sentence:** {sentence.text}")
        lines.append("")
        lines.append(
            f"**Verdict:** {verdict.overall_assessment} (confidence {verdict.confidence:.2f})"
        )

        if verdict.suggested_rewording:
            lines.append("")
            lines.append(f"**Suggested rewording:** {verdict.suggested_rewording}")

        if verdict.synthesis:
            lines.append("")
            lines.append("**Synthesis:**")
            lines.append("")
            lines.append(verdict.synthesis)

        primary_evaluations = verdict.get_primary_evaluations(evaluations)
        if primary_evaluations:
            lines.append("")
            lines.append("**Recommended references:**")
            lines.append("")
            for evaluation in primary_evaluations:
                lines.append(f"- {evaluation.article}")
        else:
            lines.append("")
            lines.append("**Recommended references:** None")

        if evaluations:
            lines.append("")
            lines.append("**Top evaluations:**")
            lines.append("")
            for evaluation in evaluations[:5]:
                lines.append(
                    f"- {evaluation.article_title} (score {evaluation.relevance_score:.2f}, "
                    f"stance {evaluation.stance or 'N/A'})"
                )

        lines.append("")

    return "\n".join(lines)


def export_sentence_evaluations_jsonl(
    results: list[tuple[Any, Any, list[Any]]],
    output_path: str,
) -> None:
    """Export per-sentence verdicts, evaluations, and articles to JSONL.

    Each JSON line contains one sentence's analysis:
    - sentence: Sentence model dump
    - verdict: FinalVerdict model dump
    - evaluations: SentenceEvaluation dumps with article_key
    - articles: mapping of article_key -> Article dump

    Args:
        results: List of (Sentence, FinalVerdict, list[SentenceEvaluation]).
        output_path: Path to write JSONL output.
    """
    with open(output_path, "w", encoding="utf-8") as handle:
        for sentence, verdict, evaluations in results:
            articles_by_key: dict[str, dict[str, Any]] = {}
            evaluation_rows: list[dict[str, Any]] = []

            for evaluation in evaluations:
                article = getattr(evaluation, "article", None)
                article_key = _article_key(article)
                if article is not None and article_key not in articles_by_key:
                    articles_by_key[article_key] = _model_dump(article)

                evaluation_row = _model_dump(evaluation)
                evaluation_row.pop("article", None)
                evaluation_row["article_key"] = article_key
                evaluation_rows.append(evaluation_row)

            record = {
                "schema_version": 1,
                "sentence": _model_dump(sentence),
                "verdict": _model_dump(verdict),
                "evaluations": evaluation_rows,
                "articles": articles_by_key,
                "primary_source_identifiers": _model_dump(
                    getattr(verdict, "primary_source_identifiers", [])
                ),
            }

            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")


def load_sentence_evaluations_jsonl(
    input_path: str,
) -> list[tuple[Any, Any, list[Any]]]:
    """Load sentence evaluations from JSONL and reconstruct models.

    Args:
        input_path: Path to JSONL file produced by export_sentence_evaluations_jsonl().

    Returns:
        List of (Sentence, FinalVerdict, list[SentenceEvaluation]).
    """
    from refweaver.evaluation_models import (
        FinalVerdict,
        SentenceEvaluation,
        SourceIdentifier,
    )
    from refweaver.models import Article, Sentence

    results: list[tuple[Any, Any, list[Any]]] = []

    with open(input_path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue

            record = json.loads(line)
            sentence = Sentence.model_validate(record["sentence"])
            verdict = FinalVerdict.model_validate(record["verdict"])
            primary_identifiers = record.get("primary_source_identifiers")
            if primary_identifiers:
                verdict = verdict.model_copy(
                    update={
                        "primary_source_identifiers": [
                            SourceIdentifier.model_validate(identifier)
                            for identifier in primary_identifiers
                        ]
                    }
                )

            articles_by_key = {
                key: Article.model_validate(value)
                for key, value in record.get("articles", {}).items()
            }

            evaluations: list[SentenceEvaluation] = []
            for row in record.get("evaluations", []):
                article_key = row.get("article_key", "unknown")
                article = articles_by_key.get(article_key)
                payload = dict(row)
                payload.pop("article_key", None)
                payload["article"] = article
                evaluations.append(SentenceEvaluation.model_validate(payload))

            results.append((sentence, verdict, evaluations))

    return results


def _article_key(article: object | None) -> str:
    """Create a stable key for an Article to preserve relationships."""
    if article is None:
        return "unknown"

    doi = getattr(article, "doi", None)
    if doi:
        return f"doi:{str(doi).strip().lower()}"

    source = getattr(article, "source", None)
    external_id = getattr(article, "external_id", None)
    if source and external_id:
        return f"{source}:{external_id}"

    title = getattr(article, "title", "")
    authors = getattr(article, "authors", [])
    year = getattr(article, "year", None)
    fingerprint = f"{title}|{authors}|{year}"
    return f"hash:{hashlib.sha1(fingerprint.encode('utf-8')).hexdigest()}"


def _model_dump(obj: Any) -> Any:
    """Best-effort conversion of a model or value into JSON-safe data."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {key: _model_dump(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_model_dump(item) for item in obj]
    return obj
