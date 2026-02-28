"""Shared reporting helpers."""

from refweaver.db.models import SentenceRecord, VerdictRecord


def build_run_report(
    run_id: str,
    sentences: list[SentenceRecord],
    verdicts: dict[str, VerdictRecord],
) -> str:
    """Build a markdown report for a run."""
    report_lines = [f"# Run {run_id}"]
    for sentence in sentences:
        verdict = verdicts.get(sentence.id)
        report_lines.append(f"- {sentence.text}")
        if verdict:
            report_lines.append(f"  - Verdict: {verdict.overall_assessment}")
    return "\n".join(report_lines)
