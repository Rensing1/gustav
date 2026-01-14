"""
Contract test: `THIRD_PARTY_NOTICES.md` must fully cover vendored assets.

Why:
    GUSTAV intentionally vendors some third-party *static* assets into this
    repository (committed to git), e.g. H5P runtime/editor assets and small
    derived override modules.

    For FOSS/compliance we require:
    - vendored snapshots are documented (at least core + editor)
    - license references are repo-stable (no `node_modules` paths)
    - referenced license text files exist in the repository

Note:
    This is a source-level contract test. It does not start Docker or execute
    the H5P sidecar.
"""

from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_third_party_notices_document_h5p_editor_snapshot() -> None:
    repo_root = _repo_root()
    notices_path = repo_root / "THIRD_PARTY_NOTICES.md"
    assert notices_path.is_file(), f"Missing notices file: {notices_path}"

    notices = notices_path.read_text(encoding="utf-8")

    # We vendor H5P editor assets into the repo; they must be documented.
    assert "## H5P Editor" in notices
    assert "h5p-service/vendor/h5p/editor/" in notices


def test_third_party_notices_license_paths_are_repo_stable_and_exist() -> None:
    repo_root = _repo_root()
    notices_path = repo_root / "THIRD_PARTY_NOTICES.md"
    assert notices_path.is_file(), f"Missing notices file: {notices_path}"

    notices = notices_path.read_text(encoding="utf-8")

    # `node_modules` is not vendored and must not be referenced from notices.
    assert "node_modules" not in notices

    # Collect all backticked paths that are used as "License text" locations.
    license_paths = re.findall(r"License text[^`]*`([^`]+)`", notices)
    assert license_paths, "No license text paths found in THIRD_PARTY_NOTICES.md"

    for rel_path in license_paths:
        license_file = repo_root / rel_path
        assert license_file.is_file(), f"License text file not found: {rel_path}"
