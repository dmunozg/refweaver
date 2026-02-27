"""Background jobs for the RefWeaver queue."""

from __future__ import annotations

from typing import Any

from refweaver.formatting import sentence_evaluations_to_markdown
from refweaver.models import Sentence
from refweaver.workflows import analyze_paragraph_with_evidence


def analyze_paragraph_job(
    paragraph: str,
    *,
    include_markdown: bool = True,
) -> dict[str, Any]:
    """Analyze a paragraph and return JSON-serializable results.

    Args:
        paragraph: Paragraph text to analyze.
        include_markdown: Whether to include a Markdown report in the response.

    Returns:
        Dict containing sentence results and optional markdown report.
    """
    results = analyze_paragraph_with_evidence(paragraph)

    serialized_results: list[dict[str, Any]] = []
    for sentence, verdict, evaluations in results:
        sentence_payload = sentence.model_dump(mode="json")
        sentence_text = (
            sentence.sentence_with_context or sentence.text
            if isinstance(sentence, Sentence)
            else str(sentence)
        )
        serialized_results.append(
            {
                "sentence": sentence_payload,
                "sentence_text": sentence_text,
                "verdict": verdict.model_dump(mode="json"),
                "evaluations": [ev.model_dump(mode="json") for ev in evaluations],
            }
        )

    response: dict[str, Any] = {"results": serialized_results}

    if include_markdown:
        response["markdown_report"] = sentence_evaluations_to_markdown(results)

    return response
