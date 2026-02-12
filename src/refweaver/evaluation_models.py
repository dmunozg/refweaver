"""Evaluation models for sentence-article analysis."""

from pydantic import BaseModel, Field


class ArticleRelevanceScore(BaseModel):
    """First-pass relevance scoring for an article against a sentence."""

    relevance_score: float = Field(
        ...,
        description="Relevance score from 0.0 (completely irrelevant) to 1.0 (highly relevant)",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of why this score was given",
    )
    key_concepts_match: list[str] = Field(
        default_factory=list,
        description="Key concepts from the sentence that match this article",
    )


class ArticleStanceEvaluation(BaseModel):
    """Detailed stance evaluation for a relevant article."""

    stance: str = Field(
        ...,
        description="Whether the article SUPPORTS, CONTRADICTS, or PARTIALLY_SUPPORTS the sentence",
        pattern=r"^(SUPPORTS|CONTRADICTS|PARTIALLY_SUPPORTS)$",
    )
    confidence: float = Field(
        ...,
        description="Confidence in the stance evaluation (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        ...,
        description="Detailed explanation with specific evidence from the article",
    )
    supporting_evidence: str | None = Field(
        None,
        description="Direct quotes or specific findings from the article that support the stance",
    )
    suggested_modification: str | None = Field(
        None,
        description="If stance is PARTIALLY_SUPPORTS or CONTRADICTS, suggest modified sentence wording",
    )


class SentenceEvaluation(BaseModel):
    """Complete evaluation of an article for a specific sentence.

    This model keeps track of the full evaluation pipeline for a single
    sentence-article pair. The article field contains the full Article object,
    and the other fields are cached metadata for convenience.
    """

    sentence: str = Field(..., description="The original sentence being evaluated")
    # Note: article field uses Any to avoid circular import issues with Pydantic v2
    # The actual type is Article from refweaver.models
    article: object = Field(..., description="The full Article object that was evaluated")
    article_title: str = Field(
        ..., description="Title of the evaluated article (cached from article)"
    )
    article_doi: str | None = Field(
        None, description="DOI of the article if available (cached from article)"
    )
    article_authors: list[str] = Field(
        default_factory=list, description="Article authors (cached from article)"
    )
    article_year: int | None = Field(None, description="Publication year (cached from article)")

    # Stage 1: Relevance scoring
    relevance_score: float = Field(
        default=0.0,
        description="Stage 1: Relevance score (0.0-1.0)",
    )
    relevance_reasoning: str = Field(
        default="",
        description="Stage 1: Reasoning for relevance score",
    )
    is_relevant: bool = Field(
        default=False,
        description="Whether article passed relevance threshold",
    )

    # Stage 2: Stance evaluation (only for relevant articles)
    stance: str | None = Field(
        default=None,
        description="Stage 2: SUPPORTS/CONTRADICTS/PARTIALLY_SUPPORTS",
    )
    stance_confidence: float | None = Field(
        default=None,
        description="Stage 2: Confidence in stance (0.0-1.0)",
    )
    stance_reasoning: str | None = Field(
        default=None,
        description="Stage 2: Detailed reasoning for stance",
    )
    supporting_evidence: str | None = Field(
        default=None,
        description="Stage 2: Specific evidence from article",
    )
    suggested_modification: str | None = Field(
        default=None,
        description="Stage 2: Suggested sentence modification if needed",
    )

    # Combined score for ranking
    @property
    def combined_score(self) -> float:
        """Combined relevance and confidence score for ranking."""
        if not self.is_relevant or self.stance_confidence is None:
            return self.relevance_score * 0.5  # Penalty for non-evaluated
        return self.relevance_score * self.stance_confidence

    def __str__(self) -> str:
        """String representation for LLM consumption."""
        lines = [
            f"Article: {self.article_title}",
            f"Authors: {', '.join(self.article_authors[:3])}{' et al.' if len(self.article_authors) > 3 else ''}",
            f"Year: {self.article_year or 'Unknown'}",
            f"Relevance: {self.relevance_score:.2f}",
        ]
        if self.stance:
            lines.extend(
                [
                    f"Stance: {self.stance} (confidence: {self.stance_confidence:.2f})",
                    f"Reasoning: {self.stance_reasoning}",
                ]
            )
            if self.supporting_evidence:
                lines.append(f"Evidence: {self.supporting_evidence[:200]}...")
            if self.suggested_modification:
                lines.append(f"Suggested modification: {self.suggested_modification}")
        return "\n".join(lines)


class SourceIdentifier(BaseModel):
    """Identifier for a source article to enable matching back to evaluations."""

    title: str = Field(..., description="Full title of the article")
    doi: str | None = Field(None, description="DOI if available (most reliable identifier)")
    index: int = Field(..., description="Original index in the evaluations list")


class FinalVerdict(BaseModel):
    """Final verdict synthesizing all evaluations."""

    overall_assessment: str = Field(
        ...,
        description="Overall assessment: WELL_SUPPORTED, PARTIALLY_SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE, or NOT_SUPPORTED",
        pattern=r"^(WELL_SUPPORTED|PARTIALLY_SUPPORTED|CONTRADICTED|INSUFFICIENT_EVIDENCE|NOT_SUPPORTED)$",
    )
    confidence: float = Field(
        ...,
        description="Overall confidence in the verdict (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    primary_sources: list[str] = Field(
        default_factory=list,
        description="Titles of the primary supporting/contradicting sources (for display)",
    )
    primary_source_identifiers: list[SourceIdentifier] = Field(
        default_factory=list,
        description="Identifiers for primary sources to enable matching back to Article objects",
    )
    synthesis: str = Field(
        ...,
        description="Synthesis of the evidence explaining the verdict",
    )
    suggested_citation: str | None = Field(
        None,
        description="Suggested citation format if sentence is supported",
    )
    suggested_rewording: str | None = Field(
        None,
        description="Suggested rewording if sentence needs modification",
    )

    def get_primary_evaluations(
        self, evaluations: list[SentenceEvaluation]
    ) -> list[SentenceEvaluation]:
        """Get the full SentenceEvaluation objects for primary sources.

        Args:
            evaluations: The full list of evaluations from which to find matches.

        Returns:
            List of SentenceEvaluation objects matching the primary sources.
        """
        matched: list[SentenceEvaluation] = []

        for identifier in self.primary_source_identifiers:
            # Try to match by DOI first (most reliable), then by title
            for ev in evaluations:
                if (
                    identifier.doi
                    and ev.article_doi == identifier.doi
                    or ev.article_title == identifier.title
                ):
                    matched.append(ev)
                    break
            else:
                # Fallback: try fuzzy match on title if exact match fails
                for ev in evaluations:
                    if identifier.title in ev.article_title or ev.article_title in identifier.title:
                        matched.append(ev)
                        break

        if matched or not self.primary_sources:
            return matched

        for source_title in self.primary_sources:
            for ev in evaluations:
                if ev.article_title == source_title:
                    matched.append(ev)
                    break
            else:
                for ev in evaluations:
                    if source_title in ev.article_title or ev.article_title in source_title:
                        matched.append(ev)
                        break

        return matched

    def get_primary_articles(self, evaluations: list[SentenceEvaluation]) -> list[object]:
        """Get the Article objects for primary sources.

        Args:
            evaluations: The full list of evaluations from which to find matches.

        Returns:
            List of Article objects matching the primary sources.
        """
        return [ev.article for ev in self.get_primary_evaluations(evaluations)]
