"""Public project-presentation contracts for the GUSTAV 0.0.4 release."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
GALLERY_IMAGES = (
    "docs/assets/readme/teacher-course-overview.jpg",
    "docs/assets/readme/teacher-authoring.jpg",
    "docs/assets/readme/course-invitation.jpg",
    "docs/assets/readme/learner-workspace.jpg",
    "docs/assets/readme/formative-feedback.jpg",
    "docs/assets/readme/practice-progress.jpg",
)


def test_readme_presents_the_0_0_4_early_alpha_release() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "Version 0.0.4" in readme
    assert "early alpha" in readme
    assert "CONTRIBUTING.md" in readme
    assert (REPO_ROOT / "CONTRIBUTING.md").is_file()


def test_readme_contains_the_complete_product_gallery() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    for relative_path in GALLERY_IMAGES:
        assert relative_path in readme
        assert (REPO_ROOT / relative_path).is_file()


def test_readme_local_markdown_targets_are_relative_and_resolvable() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    targets = re.findall(r"!?\[[^]]*\]\(([^)]+)\)", readme)

    for target in targets:
        if target.startswith(("https://", "http://", "mailto:", "#")):
            continue
        assert not target.startswith("/"), f"README target must be repository-relative: {target}"
        path_part = target.split("#", maxsplit=1)[0]
        assert (REPO_ROOT / path_part).exists(), f"README target does not exist: {target}"
