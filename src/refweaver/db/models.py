"""Database models for API persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for ORM models."""


class User(Base):
    """Minimal user record for associating runs and jobs."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    runs: Mapped[list[Run]] = relationship("Run", back_populates="user")


class Run(Base):
    """Analysis run metadata."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    input_text: Mapped[str] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship("User", back_populates="runs")
    sentences: Mapped[list[SentenceRecord]] = relationship(
        "SentenceRecord", back_populates="run", cascade="all, delete-orphan"
    )


class SentenceRecord(Base):
    """Sentence records derived from a run."""

    __tablename__ = "sentences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    sentence_with_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewrite_applied: Mapped[bool] = mapped_column(default=False)
    needs_reference: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(Text)

    run: Mapped[Run] = relationship("Run", back_populates="sentences")
    evaluations: Mapped[list[EvaluationRecord]] = relationship(
        "EvaluationRecord", back_populates="sentence", cascade="all, delete-orphan"
    )
    verdict: Mapped[VerdictRecord | None] = relationship(
        "VerdictRecord", back_populates="sentence", uselist=False, cascade="all, delete-orphan"
    )


class ArticleRecord(Base):
    """Article metadata associated with evaluations."""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(JSON, default=list)
    year: Mapped[int | None] = mapped_column(nullable=True)
    doi: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluations: Mapped[list[EvaluationRecord]] = relationship(
        "EvaluationRecord", back_populates="article", cascade="all, delete-orphan"
    )


class EvaluationRecord(Base):
    """Evaluation results for a sentence and article pairing."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sentence_id: Mapped[str] = mapped_column(ForeignKey("sentences.id"), index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), index=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_relevant: Mapped[bool] = mapped_column(default=False)
    stance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stance_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    stance_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_modification: Mapped[str | None] = mapped_column(Text, nullable=True)

    sentence: Mapped[SentenceRecord] = relationship("SentenceRecord", back_populates="evaluations")
    article: Mapped[ArticleRecord] = relationship("ArticleRecord", back_populates="evaluations")


class VerdictRecord(Base):
    """Final verdict per sentence."""

    __tablename__ = "verdicts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sentence_id: Mapped[str] = mapped_column(ForeignKey("sentences.id"), unique=True)
    overall_assessment: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    primary_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    primary_source_identifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    synthesis: Mapped[str] = mapped_column(Text)
    suggested_citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_rewording: Mapped[str | None] = mapped_column(Text, nullable=True)

    sentence: Mapped[SentenceRecord] = relationship("SentenceRecord", back_populates="verdict")
