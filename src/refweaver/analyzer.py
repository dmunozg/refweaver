"""Sentence analysis pipeline for RefWeaver.

Analyzes sentences from manuscript paragraphs to determine if they need references.
"""

from typing import List

from loguru import logger

from refweaver.llm import LLMClient
from refweaver.models import Article, Sentence
from refweaver.text_utils import split_sentences


class SentenceAnalyzer:
    """Analyzes sentences to determine if they need references."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize the sentence analyzer.

        Args:
            llm_client: LLM client for analysis. If None, creates a new instance.
        """
        self.llm = llm_client or LLMClient()
        logger.info("SentenceAnalyzer initialized")

    def analyze_paragraph(self, paragraph: str) -> List[Sentence]:
        """Analyze all sentences in a paragraph.

        Args:
            paragraph: Paragraph text to analyze.

        Returns:
            List of Sentence objects with reference analysis.
        """
        sentences = split_sentences(paragraph)
        results: List[Sentence] = []

        for sent_text in sentences:
            analysis = self.llm.analyze_sentence_needs_reference(
                sentence=sent_text,
                context=paragraph,
            )
            sentence = Sentence(
                text=sent_text,
                needs_reference=bool(analysis["needs_reference"]),
                reason=str(analysis["reason"]),
            )
            results.append(sentence)
            logger.debug(
                f"Analyzed: '{sent_text[:50]}...' -> "
                f"needs_reference={sentence.needs_reference}"
            )

        logger.info(f"Analyzed {len(results)} sentences in paragraph")
        return results

    def analyze_sentences(self, text: str) -> List[Sentence]:
        """Analyze all sentences in a text (paragraphs are processed together).

        This is a convenience method that splits text into paragraphs,
        then analyzes all sentences across all paragraphs.

        Args:
            text: Full text to analyze (can be multiple paragraphs).

        Returns:
            List of Sentence objects with reference analysis.
        """
        from refweaver.text_utils import split_paragraphs

        paragraphs = split_paragraphs(text)
        all_sentences: List[Sentence] = []

        for para in paragraphs:
            sentences = self.analyze_paragraph(para)
            all_sentences.extend(sentences)

        logger.info(f"Analyzed {len(all_sentences)} sentences total")
        return all_sentences

    def generate_search_keywords(self, sentence: str) -> list[str]:
        """Generate search keywords for finding supporting articles.

        Uses LLM to extract key concepts, entities, and technical terms
        from a sentence to construct effective search queries.

        Args:
            sentence: The sentence needing reference support.

        Returns:
            List of search keyword strings optimized for academic search.
        """
        prompt = f"""Generate 3-5 search keyword phrases to find academic articles that support this claim.

Sentence: {sentence}

Instructions:
1. Extract key concepts, technical terms, and named entities
2. Include specific methods, compounds, or phenomena mentioned
3. Create phrases that would appear in academic abstracts
4. Avoid generic words like "study", "research", "paper"
5. Return ONLY the keywords, one per line

Example output format:
enzyme-nanoparticle hybrid stabilization
gold nanoparticle horseradish peroxidase
protein denaturation temperature resistance

Keywords:"""

        try:
            logger.debug(f"Generating keywords for: {sentence[:60]}...")

            response = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert at constructing academic search queries. "
                            "Return concise, specific keyword phrases."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=256,
                temperature=0.1,
            )

            result = response.choices[0].message.content
            if not result:
                logger.warning("LLM returned empty keywords, using fallback")
                return [sentence[:100]]

            # Parse keywords from response
            keywords = [
                line.strip()
                for line in result.strip().split("\n")
                if line.strip() and not line.strip().startswith(("Keywords:", "-", "*"))
            ]

            if not keywords:
                logger.warning("No keywords extracted, using fallback")
                return [sentence[:100]]

            logger.info(f"Generated {len(keywords)} keywords: {keywords}")
            return keywords

        except Exception as e:
            logger.error(f"Keyword generation failed: {e}")
            return [sentence[:100]]  # Fallback to truncated sentence

    def evaluate_article_relevance(
        self,
        sentence: str,
        article: Article,
    ) -> dict[str, bool | str | float]:
        """Evaluate if an article is relevant to support a sentence.

        Uses LLM to compare the sentence's claim against the article's
        title and abstract to determine relevance.

        Args:
            sentence: The claim needing support.
            article: The candidate article to evaluate.

        Returns:
            Dict with 'relevant' (bool), 'confidence' (float 0-1),
            and 'reasoning' (str) explaining the decision.
        """
        abstract = article.abstract or "[Abstract not available]"

        prompt = f"""Evaluate if this article supports the following claim.

CLAIM TO SUPPORT:
{sentence}

ARTICLE:
Title: {article.title}
Authors: {', '.join(article.authors[:3])}{', et al.' if len(article.authors) > 3 else ''}
Year: {article.year or 'Unknown'}
Abstract: {abstract[:1500]}

INSTRUCTIONS:
Determine if this article provides evidence that DIRECTLY SUPPORTS the claim.
- The article doesn't need to say exactly the same thing
- It should provide supporting evidence, data, or establish the foundation for the claim
- Consider if the article's findings are relevant and applicable

Respond in this EXACT format:
RELEVANT: [YES/NO/Maybe]
CONFIDENCE: [0.0-1.0]
REASONING: [Brief explanation of why this article does or doesn't support the claim]
"""

        try:
            logger.debug(f"Evaluating article '{article.title[:50]}...' for relevance")

            response = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert scientific reviewer evaluating "
                            "if research articles support specific claims."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=512,
                temperature=0.0,
            )

            result = response.choices[0].message.content
            if not result:
                return {
                    "relevant": False,
                    "confidence": 0.0,
                    "reasoning": "Empty response from LLM",
                }

            # Parse response
            relevant = False
            confidence = 0.0
            reasoning = "Unable to parse response"

            for line in result.strip().split("\n"):
                line = line.strip()
                if line.startswith("RELEVANT:"):
                    val = line.split(":", 1)[1].strip().upper()
                    relevant = val in ("YES", "MAYBE")
                elif line.startswith("CONFIDENCE:"):
                    try:
                        val = line.split(":", 1)[1].strip()
                        confidence = float(val)
                    except (ValueError, IndexError):
                        confidence = 0.0
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()

            # Ensure confidence is in valid range
            confidence = max(0.0, min(1.0, confidence))

            logger.info(
                f"Article relevance: relevant={relevant}, "
                f"confidence={confidence:.2f}"
            )

            return {
                "relevant": relevant,
                "confidence": confidence,
                "reasoning": reasoning,
            }

        except Exception as e:
            logger.error(f"Article relevance evaluation failed: {e}")
            return {
                "relevant": False,
                "confidence": 0.0,
                "reasoning": f"Error during evaluation: {e}",
            }
