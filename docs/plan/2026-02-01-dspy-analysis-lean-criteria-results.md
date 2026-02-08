# Plan: DSPy Analysis – Lean `criteria_results[]` Model Output (remove `max_score`)

## Context
GUSTAV uses a two-step DSPy pipeline for learning feedback:
1. **Rubric analysis** → a structured `criteria.v2` payload (`criteria_results[]`)
2. **Feedback synthesis** → a short formative Markdown text

The canonical analysis payload (`criteria.v2`) is currently shaped like:
- `schema`: `"criteria.v2"`
- `score`: overall score (0..5) derived from per-criterion results
- `criteria_results[]`: list of objects with
  - `criterion` (string)
  - `max_score` (int, usually `10`)
  - `score` (int, 0..10)
  - `explanation_md` (Markdown, evidence-based; **no length limit planned**)

### What we observed
- The overall score is already derived in Python (`_derive_overall_score`) and must **not** be model output.
- `max_score` is typically constant (`10`) and therefore redundant to generate for every criterion.
- In benchmarking, we want to compare “structured output enforced” vs “free text JSON” fairly and with minimal output redundancy.

## Decision (Scope of this plan)
- We remove **`max_score` from the model output contract** (DSPy signature output), but:
  - we keep `max_score` in the canonical `criteria.v2` payload by filling it server-side (default `10`)
  - we keep the overall `analysis.score` field (0..5) **derived** for backwards compatibility
- We do **not** limit `explanation_md`.
- We do **not** introduce stable criterion IDs (no “spelling”, etc.).

## Goal
Reduce redundant output tokens and (potentially) structured-output constraint overhead by requiring the model to generate only what it must:
- per-criterion `score`
- per-criterion `explanation_md`

While preserving the existing, stable `criteria.v2` contract used by the app and UI.

## User Story
As a developer/operator, I want the DSPy analysis stage to avoid generating redundant fields like `max_score`,
so the analysis stage becomes faster/cheaper and less fragile, without breaking the rest of GUSTAV which consumes `criteria.v2`.

## BDD Scenarios (Given–When–Then)

### 1) Structured analysis works with lean model output
Given the model returns `criteria_results[]` items **without** `max_score`  
When `run_structured_analysis(...)` is executed  
Then the returned analysis is valid `criteria.v2`  
And each `criteria_results[i].max_score` is set to `10` server-side  
And the overall `analysis.score` is derived (0..5) from per-criterion scores.

### 2) Normalization keeps canonical shape (ordering + defaults)
Given analysis output is missing `max_score` for some or all items  
When `_normalize_v2(...)` runs  
Then it emits `criteria.v2` with stable ordering matching the input `criteria` list  
And missing values are filled with defaults (`max_score=10`, `score=0` if missing)  
And `explanation_md` is kept as-is (no truncation).

### 3) Benchmark comparability remains fair across runs
Given two benchmark runs that differ only by `--structured-output on|off`  
When we compare throughput/latency  
Then differences are not dominated by cross-run cache reuse  
And `--cache on` uses a fresh per-run `DSPY_CACHEDIR` to avoid cross-run cache hits.

## Implementation Notes (TDD / Red-Green-Refactor)
1. **Red (tests first):**
   - Add a failing unit test that simulates DSPy returning `criteria_results` items without `max_score`.
   - Assert that our adapter returns canonical `criteria.v2` with `max_score=10` and derived overall `score`.
2. **Green (minimal change):**
   - Introduce a “lean” DTO for DSPy output (e.g. `LeanCriterionResult`) that omits `max_score`.
   - Update DSPy signatures to output `list[LeanCriterionResult]` for the analysis stage.
   - Convert lean results into full `CriterionResult(max_score=10, ...)` in `run_structured_analysis`.
3. **Refactor (keep it readable):**
   - Ensure docstrings/prompts mention that `max_score` is fixed server-side.
   - Update any affected tests and keep naming consistent (`criteria.v2` everywhere).

## Open Questions (optional follow-ups, not required for this plan)
- Should the model also omit `criterion` and rely on the given criteria order to map results?
  - This can save more tokens (no IDs needed), but requires stricter ordering assumptions and careful normalization.
- Should we add JSON-repair logic for unstructured benchmark mode to reduce failures from minor JSON glitches?

## Success Criteria
- The app/UI still receives a valid `criteria.v2` payload with `max_score` present (default 10).
- The analysis stage produces fewer output tokens than before (measurable in benchmarks).
- No regressions in alignment/ordering of `criteria_results[]`.

