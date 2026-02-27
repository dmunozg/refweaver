"""Background jobs for the RefWeaver queue."""

from __future__ import annotations

import os
from typing import Any

from loguru import logger

from refweaver.db.persist import persist_run_results
from refweaver.db.session import get_session
from refweaver.formatting import sentence_evaluations_to_markdown
from refweaver.models import Sentence
from refweaver.workflows import analyze_paragraph_with_evidence


def analyze_paragraph_job(
    paragraph: str,
    *,
    run_id: str,
    user_id: str,
    include_markdown: bool = True,
) -> dict[str, Any]:
    """Analyze a paragraph and return JSON-serializable results.

    Args:
        paragraph: Paragraph text to analyze.
        run_id: Identifier for the analysis run.
        user_id: Identifier for the requesting user.
        include_markdown: Whether to include a Markdown report in the response.

    Returns:
        Dict containing sentence results and optional markdown report.
    """
    results = analyze_paragraph_with_evidence(paragraph)
    try:
        session = get_session(os.getenv("DATABASE_URL", "sqlite:///./refweaver.db"))
        persist_run_results(
            session,
            run_id=run_id,
            user_id=user_id,
            mode="paragraph",
            input_text=paragraph,
            results=results,
        )
    except Exception as exc:
        logger.exception("Failed to persist run results", exc_info=exc)

    serialized_results: list[dict[str, Any]] = []
    for sentence, verdict, evaluations in results:
        sentence_payload = sentence.model_dump(mode="json")
        if isinstance(sentence, Sentence):
            sentence_for_evaluation = sentence.sentence_with_context or sentence.text
            sentence_original_text = sentence.text
        else:
            sentence_for_evaluation = str(sentence)
            sentence_original_text = sentence_for_evaluation
        serialized_results.append(
            {
                "sentence": sentence_payload,
                "sentence_for_evaluation": sentence_for_evaluation,
                "sentence_original_text": sentence_original_text,
                "verdict": verdict.model_dump(mode="json"),
                "evaluations": [ev.model_dump(mode="json") for ev in evaluations],
            }
        )

    response: dict[str, Any] = {
        "run_id": run_id,
        "user_id": user_id,
        "results": serialized_results,
    }

    if include_markdown:
        response["markdown_report"] = sentence_evaluations_to_markdown(results)

    return response
