from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_visual_smoke_specs_are_tagged_and_not_snapshot_based() -> None:
    e2e_dir = REPO_ROOT / "frontend" / "e2e"
    specs = sorted(e2e_dir.glob("*.spec.ts"))
    visual_specs = [path for path in specs if "@visual-smoke" in path.read_text(encoding="utf-8")]

    assert visual_specs, "Expected at least one Playwright spec tagged with @visual-smoke"

    combined = "\n".join(path.read_text(encoding="utf-8") for path in visual_specs)
    assert "toHaveScreenshot" not in combined
    assert "toMatchSnapshot" not in combined
