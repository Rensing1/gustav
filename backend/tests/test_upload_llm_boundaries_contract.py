from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_upload_llm_boundary_documents_preserve_original_submission_rule() -> None:
    """PR 4 must not redefine LLM safety as hidden content rewriting."""

    plan = _read("docs/plan/2026-07-02-upload-llm-boundaries.md")
    security = _read("docs/harness/SECURITY_BASELINE.md")
    combined = f"{plan}\n{security}"

    for required_phrase in (
        "nicht inhaltlich geprüft",
        "nicht gefiltert",
        "nicht normalisiert",
        "nicht moderiert",
        "nicht umgeschrieben",
        "originalen Schülerinhalt",
        "Technische Verpackung ist erlaubt",
        "gespeicherte Original bleibt unverändert",
    ):
        assert required_phrase in combined


def test_upload_llm_boundary_plan_links_to_dedicated_gate() -> None:
    """The product decision needs an executable local signal."""

    plan = _read("docs/plan/2026-07-02-upload-llm-boundaries.md")
    quality_gates = _read("docs/harness/QUALITY_GATES.md")

    assert "make test-upload-llm-boundaries" in plan
    assert "test-upload-llm-boundaries" in quality_gates
