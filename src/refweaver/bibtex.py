"""BibTeX export utilities for RefWeaver."""

from datetime import datetime
from pathlib import Path

from refweaver.models import Article


def export_to_bibtex(
    articles: list[Article],
    output_path: str | Path,
    title: str | None = None,
) -> Path:
    """Export a list of articles to a BibTeX file.

    Args:
        articles: List of Article objects to export.
        output_path: Path to the output .bib file.
        title: Optional header comment for the file.

    Returns:
        Path to the created file.
    """
    output_path = Path(output_path)

    lines: list[str] = []

    # Header comment
    lines.append("%" + "=" * 60)
    if title:
        lines.append(f"% {title}")
    else:
        lines.append("% BibTeX export from RefWeaver")
    lines.append(f"% Generated: {datetime.now().isoformat()}")
    lines.append("%" + "=" * 60)
    lines.append("")

    # Export each article
    for i, article in enumerate(articles, 1):
        # Generate unique cite key
        cite_key = article._generate_cite_key()
        # Add suffix if duplicate
        if i > 1:
            cite_key = f"{cite_key}_{i}"

        lines.append(f"% Entry {i}: {article.title[:50]}...")
        lines.append(article.to_bibtex(cite_key=cite_key))
        lines.append("")

    # Write file
    output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path


def export_analysis_results(
    results: list[dict],
    output_path: str | Path,
    include_insufficient: bool = False,
) -> Path:
    """Export analysis results to BibTeX.

    Args:
        results: List of result dicts with 'article' and 'assessment' keys.
        output_path: Path to output .bib file.
        include_insufficient: Whether to include INSUFFICIENT_INFO results.

    Returns:
        Path to created file.
    """
    output_path = Path(output_path)

    # Filter to supporting articles only (unless include_insufficient)
    filtered_results = []
    for result in results:
        verdict = result.get("assessment", {}).get("verdict", "")
        if verdict in ("SUPPORTS", "PARTIALLY_SUPPORTS"):
            filtered_results.append(result)
        elif include_insufficient and verdict == "INSUFFICIENT_INFO":
            filtered_results.append(result)

    articles = [r["article"] for r in filtered_results]

    # Add notes about verdicts
    lines: list[str] = []
    lines.append("%" + "=" * 60)
    lines.append("% RefWeaver Analysis Results")
    lines.append(f"% Generated: {datetime.now().isoformat()}")
    lines.append(f"% Total supporting articles: {len(filtered_results)}")
    lines.append("%" + "=" * 60)
    lines.append("")

    for i, result in enumerate(filtered_results, 1):
        article = result["article"]
        assessment = result["assessment"]

        lines.append(f"% Entry {i}: {assessment.get('verdict', 'UNKNOWN')}")
        lines.append(f"% Confidence: {assessment.get('confidence', 0.0):.2f}")
        if assessment.get("reasoning"):
            reasoning = assessment["reasoning"].replace("\n", " ")
            lines.append(f"% Reasoning: {reasoning[:200]}...")
        lines.append("")

        cite_key = article._generate_cite_key()
        if i > 1:
            cite_key = f"{cite_key}_{i}"

        lines.append(article.to_bibtex(cite_key=cite_key))
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path
