"""The CLI and project configuration must enforce the same lint policy."""

import tomllib
from pathlib import Path


def test_ruff_centrally_enforces_errors_imports_and_pyflakes_without_line_wrapping():
    config = tomllib.loads((Path(__file__).resolve().parents[3] / "pyproject.toml").read_text())
    lint = config["tool"]["ruff"]["lint"]
    assert set(lint["select"]) == {"E", "F", "I"}
    assert lint.get("ignore") == ["E501"]
