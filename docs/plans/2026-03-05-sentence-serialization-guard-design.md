# Sentence Serialization Guard Design

## Goal
Prevent serialization failures in `analyze_paragraph_job` when a result contains a non-`Sentence` value by guarding `model_dump` and emitting a string fallback.

## Architecture
- Keep `analyze_paragraph_job` as the serialization boundary.
- Add a type guard before calling `Sentence.model_dump`.
- Preserve structured payloads for `Sentence` instances while allowing rare non-`Sentence` values.

## Data Flow
- Iterate `results` as today.
- If `sentence` is `Sentence`, serialize with `model_dump(mode="json")`.
- Otherwise, set the `sentence` payload to `str(sentence)`.
- Always populate `sentence_for_evaluation` and `sentence_original_text` from the guarded branch.

## Error Handling
- Avoid raising on non-`Sentence` values; no new exceptions added.

## Testing
- Run `pytest` after implementation.
