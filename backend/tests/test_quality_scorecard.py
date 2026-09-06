"""Keep repeated monthly snapshots comparable and public-repository safe."""

from backend.tools import quality_scorecard as scorecard


def test_repeated_snapshot_compares_with_previous_month_only(tmp_path, monkeypatch):
    (tmp_path / "example.py").write_text("one\ntwo\nthree\n")
    monkeypatch.setattr(scorecard, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "DEFAULT_HOTSPOTS", ["example.py"])
    history = [
        {"month": "2026-08", "hotspots": [{"path": "example.py", "loc": 1}]},
        {"month": "2026-09", "hotspots": [{"path": "example.py", "loc": 3}]},
        {"month": "2026-10", "hotspots": [{"path": "example.py", "loc": 9}]},
    ]
    assert scorecard._collect_hotspots(history, month="2026-09") == [("example.py", 3, 2)]


def test_public_command_uses_repository_relative_paths():
    command = [str(scorecard.REPO_ROOT / ".venv/bin/python"), "--spec", str(scorecard.REPO_ROOT / "api/openapi.yml")]
    assert scorecard._display_command(command) == ".venv/bin/python --spec api/openapi.yml"
