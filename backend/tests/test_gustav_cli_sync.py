from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from backend.tools.gustav_cli import cli, config
from backend.tools.gustav_cli.sync_engine import (
    ChangeOrigin,
    compare_snapshots,
    requires_prune,
    snapshot_digest,
)
from backend.tools.gustav_cli.sync_manifest import load_local_snapshot, write_local_snapshot

BASE_URL = "https://gustav.example"
TOKEN = "gustav_cli_token_secret"


def _unit(*, title: str = "Binärzahlen") -> dict[str, object]:
    return {
        "key": "binaerzahlen",
        "unit_type": "linear",
        "title": title,
        "summary": "Eine Einführung",
        "sections": [
            {
                "key": "einstieg",
                "title": "Einstieg",
                "materials": [
                    {
                        "key": "stellenwerte",
                        "kind": "markdown",
                        "title": "Stellenwerte",
                        "body_md": "Zweierpotenzen.",
                    }
                ],
                "tasks": [
                    {
                        "key": "umrechnen",
                        "kind": "native",
                        "instruction_md": "Rechne 1010 um.",
                        "criteria": ["korrektes Ergebnis"],
                        "teacher_context_md": None,
                        "model_solution_md": None,
                        "due_at": None,
                        "max_attempts": None,
                    }
                ],
            }
        ],
    }


def _snapshot(*, title: str = "Binärzahlen") -> dict[str, object]:
    return {"schema_version": 1, "units": {"binaerzahlen": _unit(title=title)}}


def _snapshot_with_two_units() -> dict[str, object]:
    first = deepcopy(_unit())
    second = deepcopy(_unit(title="Logikgatter"))
    second["key"] = "logikgatter"
    return {
        "schema_version": 1,
        "units": {"binaerzahlen": first, "logikgatter": second},
    }


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path / "config"))
    config.save_config(config.GustavCLIConfig(base_url=BASE_URL, token=TOKEN))


def test_manifest_roundtrip_uses_yaml_and_markdown_files(tmp_path: Path) -> None:
    write_local_snapshot(tmp_path, _snapshot(), base_url=BASE_URL)

    loaded = load_local_snapshot(tmp_path, expected_base_url=BASE_URL)

    assert loaded == _snapshot()
    assert (tmp_path / "gustav.yaml").is_file()
    unit_dir = tmp_path / "units" / "binaerzahlen"
    assert (unit_dir / "unit.yaml").is_file()
    assert (unit_dir / "content" / "einstieg" / "materials" / "stellenwerte.md").read_text(
        encoding="utf-8"
    ) == "Zweierpotenzen.\n"
    assert (unit_dir / "content" / "einstieg" / "tasks" / "umrechnen" / "instruction.md").read_text(
        encoding="utf-8"
    ) == "Rechne 1010 um.\n"


def test_manifest_rejects_paths_outside_unit_and_symlinks(tmp_path: Path) -> None:
    write_local_snapshot(tmp_path, _snapshot(), base_url=BASE_URL)
    unit_file = tmp_path / "units" / "binaerzahlen" / "unit.yaml"
    text = unit_file.read_text(encoding="utf-8")
    unit_file.write_text(
        text.replace("materials/stellenwerte.md", "../../outside.md"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="unsafe_local_path"):
        load_local_snapshot(tmp_path, expected_base_url=BASE_URL)


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    write_local_snapshot(tmp_path, _snapshot(), base_url=BASE_URL)
    unit_file = tmp_path / "units" / "binaerzahlen" / "unit.yaml"
    text = unit_file.read_text(encoding="utf-8")
    unit_file.write_text(text + "titel: Tippfehler\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown_unit_field"):
        load_local_snapshot(tmp_path, expected_base_url=BASE_URL)

    write_local_snapshot(tmp_path, _snapshot(), base_url=BASE_URL)
    material = (
        tmp_path
        / "units"
        / "binaerzahlen"
        / "content"
        / "einstieg"
        / "materials"
        / "stellenwerte.md"
    )
    material.unlink()
    material.symlink_to(tmp_path / "gustav.yaml")
    with pytest.raises(ValueError, match="unsafe_local_path"):
        load_local_snapshot(tmp_path, expected_base_url=BASE_URL)


def test_manifest_roundtrip_preserves_file_simulation_and_h5p_assets(tmp_path: Path) -> None:
    h5p_path = tmp_path / "source.h5p"
    with zipfile.ZipFile(h5p_path, "w") as archive:
        archive.writestr("h5p.json", '{"title":"Quiz"}')
        archive.writestr("content/content.json", '{"question":"2+2"}')
    unit = _unit()
    section = unit["sections"][0]
    section["materials"].extend(
        [
            {
                "key": "arbeitsblatt",
                "kind": "file",
                "title": "Arbeitsblatt",
                "filename_original": "blatt.pdf",
                "mime_type": "application/pdf",
                "alt_text": "Aufgabenblatt",
                "_asset_bytes": b"%PDF-demo",
            },
            {
                "key": "simulation",
                "kind": "simulation",
                "title": "Simulation",
                "filename_original": "modell.html",
                "mime_type": "text/html",
                "body_md": "Orientierung",
                "_asset_bytes": b"<!doctype html><title>Modell</title>",
            },
        ]
    )
    section["tasks"].append(
        {
            "key": "quiz",
            "kind": "h5p",
            "instruction_md": "Bearbeite das Quiz.",
            "criteria": [],
            "teacher_context_md": None,
            "model_solution_md": None,
            "due_at": None,
            "max_attempts": None,
            "display_options": {},
            "_h5p_bytes": h5p_path.read_bytes(),
        }
    )
    snapshot = {"schema_version": 1, "units": {"binaerzahlen": unit}}

    write_local_snapshot(tmp_path / "mirror", snapshot, base_url=BASE_URL)
    loaded = load_local_snapshot(tmp_path / "mirror", expected_base_url=BASE_URL)

    materials = loaded["units"]["binaerzahlen"]["sections"][0]["materials"]
    assert materials[1]["sha256"]
    assert materials[1]["size_bytes"] == len(b"%PDF-demo")
    assert materials[2]["sha256"]
    quiz = loaded["units"]["binaerzahlen"]["sections"][0]["tasks"][1]
    assert quiz["h5p_sha256"]
    assert materials[1]["_asset_bytes"] == b"%PDF-demo"


def test_three_way_comparison_classifies_clean_local_remote_and_diverged() -> None:
    base = _snapshot()

    assert compare_snapshots(base, base, base).origin is ChangeOrigin.CLEAN
    assert compare_snapshots(base, _snapshot(title="Lokal"), base).origin is ChangeOrigin.LOCAL
    assert compare_snapshots(base, base, _snapshot(title="Extern")).origin is ChangeOrigin.REMOTE
    assert (
        compare_snapshots(base, _snapshot(title="Lokal"), _snapshot(title="Extern")).origin
        is ChangeOrigin.DIVERGED
    )


def test_prune_detection_covers_units_and_nested_objects() -> None:
    target = _snapshot()
    assert requires_prune({"schema_version": 1, "units": {}}, target) is True

    source = _snapshot()
    source["units"]["binaerzahlen"]["sections"][0]["materials"] = []
    assert requires_prune(source, target) is True
    assert requires_prune(_snapshot(title="Geändert"), target) is False

    old_file = _snapshot()
    new_file = _snapshot()
    old_materials = old_file["units"]["binaerzahlen"]["sections"][0]["materials"]
    new_materials = new_file["units"]["binaerzahlen"]["sections"][0]["materials"]
    old_materials[0] = {
        "key": "datei",
        "kind": "file",
        "title": "Datei",
        "sha256": "old",
    }
    new_materials[0] = {
        "key": "datei",
        "kind": "file",
        "title": "Datei",
        "sha256": "new",
    }
    assert requires_prune(new_file, old_file) is True


def test_sync_status_reports_drift_without_mutating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path / "config"))
    config.save_config(config.GustavCLIConfig(base_url=BASE_URL, token=TOKEN))
    mirror = tmp_path / "mirror"
    write_local_snapshot(mirror, _snapshot(title="Lokal"), base_url=BASE_URL)
    state_dir = mirror / ".gustav"
    state_dir.mkdir()
    (state_dir / "state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_url": BASE_URL,
                "owner_sub": "teacher-1",
                "base_digest": snapshot_digest(_snapshot()),
                "mapping": {},
            }
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def read_owner_sub(self) -> str:
            return "teacher-1"

        def fetch_snapshot(self, mapping):
            return _snapshot()

    monkeypatch.setattr("backend.tools.gustav_cli.sync.GustavSyncClient", FakeClient)
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = cli.main(
        ["sync", "status", "--root", str(mirror), "--json"],
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 2
    assert stderr.getvalue() == ""
    report = json.loads(stdout.getvalue())
    assert report["origin"] == "local"
    assert report["pull_blocked"] is True
    assert report["push_blocked"] is False
    assert json.loads((state_dir / "state.json").read_text(encoding="utf-8"))[
        "base_digest"
    ] == snapshot_digest(_snapshot())


def test_initial_pull_creates_bound_mirror_and_digest_only_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(tmp_path, monkeypatch)
    mirror = tmp_path / "mirror"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def read_owner_sub(self) -> str:
            return "teacher-1"

        def fetch_snapshot(self, mapping, *, include_assets=False):
            assert mapping == {}
            assert include_assets is True
            return _snapshot(), {"units": {"binaerzahlen": {"remote_id": "unit-1"}}}

    monkeypatch.setattr("backend.tools.gustav_cli.sync.GustavSyncClient", FakeClient)

    code, stdout, stderr = _run(["sync", "pull", "--root", str(mirror), "--json"])

    assert code == 0, stderr
    assert json.loads(stdout)["origin"] == "remote"
    assert load_local_snapshot(mirror, expected_base_url=BASE_URL) == _snapshot()
    state = json.loads((mirror / ".gustav" / "state.json").read_text(encoding="utf-8"))
    assert state["owner_sub"] == "teacher-1"
    assert state["base_digest"] == snapshot_digest(_snapshot())
    assert "base" not in state
    assert "Binärzahlen" not in json.dumps(state, ensure_ascii=False)


def test_unit_filter_pulls_and_compares_only_the_selected_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(tmp_path, monkeypatch)
    mirror = tmp_path / "mirror"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def read_owner_sub(self) -> str:
            return "teacher-1"

        def fetch_snapshot(self, mapping, *, include_assets=False):
            return _snapshot_with_two_units(), {
                "units": {
                    "binaerzahlen": {"remote_id": "unit-1"},
                    "logikgatter": {"remote_id": "unit-2"},
                }
            }

    monkeypatch.setattr("backend.tools.gustav_cli.sync.GustavSyncClient", FakeClient)

    pulled, _, pull_error = _run(["sync", "pull", "--root", str(mirror), "--unit", "unit-2"])
    status, _, status_error = _run(
        ["sync", "status", "--root", str(mirror), "--unit", "logikgatter"]
    )

    assert pulled == 0, pull_error
    assert status == 0, status_error
    local = load_local_snapshot(mirror, expected_base_url=BASE_URL)
    assert set(local["units"]) == {"logikgatter"}
    state = json.loads((mirror / ".gustav" / "state.json").read_text(encoding="utf-8"))
    assert set(state["base_unit_digests"]) == {"logikgatter"}


def test_pull_refuses_local_drift_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(tmp_path, monkeypatch)
    mirror = tmp_path / "mirror"
    write_local_snapshot(mirror, _snapshot(title="Lokal"), base_url=BASE_URL)
    state_dir = mirror / ".gustav"
    state_dir.mkdir()
    state_dir.joinpath("state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_url": BASE_URL,
                "owner_sub": "teacher-1",
                "base_digest": snapshot_digest(_snapshot()),
                "mapping": {},
            }
        ),
        encoding="utf-8",
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def read_owner_sub(self):
            return "teacher-1"

        def fetch_snapshot(self, mapping, *, include_assets=False):
            return _snapshot(title="Extern"), mapping

    monkeypatch.setattr("backend.tools.gustav_cli.sync.GustavSyncClient", FakeClient)

    code, _, stderr = _run(["sync", "pull", "--root", str(mirror)])

    assert code == 1
    assert "--discard-local" in stderr
    assert load_local_snapshot(mirror, expected_base_url=BASE_URL) == _snapshot(title="Lokal")


def test_push_refuses_remote_drift_and_pushes_local_change_when_remote_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(tmp_path, monkeypatch)
    mirror = tmp_path / "mirror"
    write_local_snapshot(mirror, _snapshot(title="Lokal"), base_url=BASE_URL)
    state_dir = mirror / ".gustav"
    state_dir.mkdir()
    state = {
        "schema_version": 1,
        "base_url": BASE_URL,
        "owner_sub": "teacher-1",
        "base_digest": snapshot_digest(_snapshot()),
        "mapping": {},
    }
    state_dir.joinpath("state.json").write_text(json.dumps(state), encoding="utf-8")
    pushed: list[dict[str, object]] = []

    class FakeClient:
        remote = _snapshot(title="Extern")

        def __init__(self, *args, **kwargs):
            pass

        def read_owner_sub(self):
            return "teacher-1"

        def fetch_snapshot(self, mapping, *, include_assets=False):
            return self.remote, mapping

        def push_snapshot(self, local, remote, mapping, *, prune, checkpoint):
            pushed.append(local)
            self.__class__.remote = local
            checkpoint(mapping)
            return mapping

    monkeypatch.setattr("backend.tools.gustav_cli.sync.GustavSyncClient", FakeClient)

    blocked, _, blocked_error = _run(["sync", "push", "--root", str(mirror)])
    assert blocked == 1
    assert "--overwrite-remote" in blocked_error
    assert pushed == []

    FakeClient.remote = _snapshot()
    code, stdout, stderr = _run(["sync", "push", "--root", str(mirror), "--json"])
    assert code == 0, stderr
    assert pushed == [_snapshot(title="Lokal")]
    assert json.loads(stdout)["origin"] == "local"
    updated = json.loads(state_dir.joinpath("state.json").read_text(encoding="utf-8"))
    assert updated["base_digest"] == snapshot_digest(_snapshot(title="Lokal"))


def test_sync_reports_remote_api_errors_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(tmp_path, monkeypatch)
    mirror = tmp_path / "mirror"
    write_local_snapshot(mirror, _snapshot(), base_url=BASE_URL)
    state_dir = mirror / ".gustav"
    state_dir.mkdir()
    state_dir.joinpath("state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_url": BASE_URL,
                "owner_sub": "teacher-1",
                "base_digest": snapshot_digest(_snapshot()),
                "mapping": {},
            }
        ),
        encoding="utf-8",
    )

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def read_owner_sub(self) -> str:
            raise RuntimeError("remote_api_error:503")

    monkeypatch.setattr("backend.tools.gustav_cli.sync.GustavSyncClient", FailingClient)

    code, _, stderr = _run(["sync", "status", "--root", str(mirror)])

    assert code == 1
    assert stderr == "Sync-Fehler: remote_api_error:503\n"


def test_push_resumes_from_a_verified_journal_without_duplicate_creates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(tmp_path, monkeypatch)
    mirror = tmp_path / "mirror"
    write_local_snapshot(mirror, _snapshot(title="Lokal"), base_url=BASE_URL)
    state_dir = mirror / ".gustav"
    state_dir.mkdir()
    state_dir.joinpath("state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_url": BASE_URL,
                "owner_sub": "teacher-1",
                "base_digest": snapshot_digest(_snapshot()),
                "mapping": {},
            }
        ),
        encoding="utf-8",
    )

    class InterruptedClient:
        remote = _snapshot()
        attempts = 0
        creates = 0

        def __init__(self, *args, **kwargs):
            pass

        def read_owner_sub(self) -> str:
            return "teacher-1"

        def fetch_snapshot(self, mapping, *, include_assets=False):
            return self.remote, mapping

        def push_snapshot(self, local, remote, mapping, *, prune, checkpoint):
            self.__class__.attempts += 1
            if self.attempts == 1:
                self.__class__.creates += 1
                self.__class__.remote = _snapshot(title="Zwischenstand")
                mapping["created"] = "remote-id"
                checkpoint(mapping)
                raise RuntimeError("remote_api_error:503")
            assert mapping["created"] == "remote-id"
            self.__class__.remote = local
            checkpoint(mapping)
            return mapping

    monkeypatch.setattr("backend.tools.gustav_cli.sync.GustavSyncClient", InterruptedClient)

    first, _, first_error = _run(["sync", "push", "--root", str(mirror)])
    second, _, second_error = _run(["sync", "push", "--root", str(mirror)])

    assert first == 1
    assert "remote_api_error:503" in first_error
    assert second == 0, second_error
    assert InterruptedClient.creates == 1
    assert not state_dir.joinpath("journal.json").exists()
