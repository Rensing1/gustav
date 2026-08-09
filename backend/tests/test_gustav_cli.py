from __future__ import annotations

import io
import json
import stat
import hashlib
from urllib.error import HTTPError

from backend.tools.gustav_cli import cli, config


def _configure_test_cli(tmp_path, monkeypatch, token: str = "gustav_cli_token_secret") -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token=token))


def _capture_http(monkeypatch, responses: list[tuple[int, object]] | None = None):
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    queued = list(responses or [(200, {})])

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return queued.pop(0) if queued else (200, {})

    monkeypatch.setattr(cli, "_http_json", fake_request)
    return calls


class _HTTPResponse:
    status = 200

    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def __enter__(self) -> "_HTTPResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def test_auth_configure_reads_token_from_stdin_and_writes_0600_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))

    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.main(
        ["auth", "configure", "--base-url", "https://gustav.example", "--token-stdin"],
        stdin=io.StringIO("gustav_cli_token_secret\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 0
    assert "konfiguriert" in stdout.getvalue()
    assert "gustav_cli_token_secret" not in stdout.getvalue()

    path = config.default_config_path()
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == {
        "base_url": "https://gustav.example",
        "token": "gustav_cli_token_secret",
    }


def test_auth_configure_rejects_non_https_base_url_without_writing_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))

    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.main(
        ["auth", "configure", "--base-url", "http://gustav.example", "--token-stdin"],
        stdin=io.StringIO("gustav_cli_token_secret\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 2
    assert "https://" in stderr.getvalue()
    assert "gustav_cli_token_secret" not in stdout.getvalue()
    assert "gustav_cli_token_secret" not in stderr.getvalue()
    assert not config.default_config_path().exists()


def test_http_json_returns_structured_body_for_non_json_success(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.urllib_request,
        "urlopen",
        lambda req, timeout: _HTTPResponse(b"plain text from proxy"),
    )

    status, body = cli._http_json("GET", "https://gustav.example/api/teaching/units")

    assert status == 200
    assert body == {"raw": "plain text from proxy"}


def test_http_json_returns_structured_body_for_non_json_http_error(monkeypatch) -> None:
    def fail_urlopen(req, timeout):
        raise HTTPError(
            "https://gustav.example/api/teaching/units",
            502,
            "Bad Gateway",
            {},
            io.BytesIO(b"<html>proxy error</html>"),
        )

    monkeypatch.setattr(cli.urllib_request, "urlopen", fail_urlopen)

    status, body = cli._http_json(
        "GET",
        "https://gustav.example/api/teaching/units",
        headers={"Authorization": "Bearer gustav_cli_secret_token"},
    )

    assert status == 502
    assert body["error"] == "http_error"
    assert body["detail"] == "Bad Gateway"
    assert body["body_preview"] == "<html>proxy error</html>"
    assert "gustav_cli_secret_token" not in str(body)


def test_http_multipart_sanitizes_content_disposition_parameters(monkeypatch) -> None:
    captured: dict[str, bytes | str | dict[str, str] | None] = {}

    def fake_http_bytes(method: str, url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        return 200, b'{"ok": true}'

    monkeypatch.setattr(cli, "_http_bytes", fake_http_bytes)

    status, body = cli._http_multipart(
        "POST",
        "https://gustav.example/api/upload",
        field_name='fi\r\neld"',
        filename='quiz"\r\nX-Injected: 1\\demo.h5p',
        content=b"PK\x03\x04",
        content_type="application/zip",
    )

    multipart_body = bytes(captured["data"]).decode("utf-8")
    assert status == 200
    assert body == {"ok": True}
    assert '\r\nX-Injected: 1' not in multipart_body
    assert 'name="fi_eld_"' in multipart_body
    assert 'filename="quiz__X-Injected: 1_demo.h5p"' in multipart_body


def test_auth_status_redacts_configured_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))

    stdout = io.StringIO()
    code = cli.main(["auth", "status"], stdout=stdout, stderr=io.StringIO())

    assert code == 0
    text = stdout.getvalue()
    assert "https://gustav.example" in text
    assert "gustav_cli_token_secret" not in text
    assert "gustav…" in text


def test_units_list_json_uses_configured_bearer_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return 200, [{"id": "unit-1", "title": "Demo", "summary": ""}]

    monkeypatch.setattr(cli, "_http_json", fake_request)

    stdout = io.StringIO()
    code = cli.main(["units", "list", "--json"], stdout=stdout, stderr=io.StringIO())

    assert code == 0
    assert json.loads(stdout.getvalue()) == [{"id": "unit-1", "title": "Demo", "summary": ""}]
    assert calls == [
        (
            "GET",
            "https://gustav.example/api/teaching/units",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        )
    ]


def test_units_create_sends_json_body(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return 201, {"id": "unit-1", "title": "Demo", "summary": "Kurz"}

    monkeypatch.setattr(cli, "_http_json", fake_request)

    stdout = io.StringIO()
    code = cli.main(
        ["units", "create", "--title", "Demo", "--description", "Kurz", "--json"],
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(stdout.getvalue())["title"] == "Demo"
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Demo", "summary": "Kurz"},
        )
    ]


def test_units_delete_requires_yes_before_http_call(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[object] = []
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: calls.append((args, kwargs)))

    stderr = io.StringIO()
    code = cli.main(["units", "delete", "unit-1"], stdout=io.StringIO(), stderr=stderr)

    assert code == 1
    assert "--yes" in stderr.getvalue()
    assert calls == []


def test_sections_reorder_sends_section_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return 200, []

    monkeypatch.setattr(cli, "_http_json", fake_request)

    code = cli.main(
        ["sections", "reorder", "--unit-id", "unit-1", "--ids", "s1", "s2"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections/reorder",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"section_ids": ["s1", "s2"]},
        )
    ]


def test_sections_list_table_prints_items(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (200, [{"id": "s1", "title": "Abschnitt 1"}]),
    )

    stdout = io.StringIO()
    code = cli.main(
        ["sections", "list", "--unit-id", "unit-1"],
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == "s1\tAbschnitt 1\n"


def test_phases_create_sends_title(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        ["phases", "create", "--unit-id", "unit-1", "--title", "Start"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/phases",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"title": "Start"},
    )


def test_modules_edge_create_uses_unit_scoped_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        ["module-edges", "create", "--unit-id", "unit-1", "--from", "m1", "--to", "m2"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/modules/edges",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"from_module_id": "m1", "to_module_id": "m2"},
    )


def test_modules_create_sends_phase_and_title(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        ["modules", "create", "--unit-id", "unit-1", "--phase-id", "phase-1", "--title", "Modul A"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/modules",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"phase_id": "phase-1", "title": "Modul A"},
    )


def test_modules_reorder_sends_module_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (200, [])),
    )

    code = cli.main(
        ["modules", "reorder", "--unit-id", "unit-1", "--phase-id", "phase-1", "--ids", "m1", "m2"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/phases/phase-1/modules/reorder",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"module_ids": ["m1", "m2"]},
    )


def test_materials_create_with_module_id_uses_module_write_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        if url.endswith("/modules/module-1/content-target"):
            return 200, {"module_id": "module-1", "section_id": "section-hidden"}
        return 201, {"id": "material-1", "title": "Hinweis"}

    monkeypatch.setattr(cli, "_http_json", fake_request)

    code = cli.main(
        [
            "materials",
            "create",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--title",
            "Hinweis",
            "--body-md",
            "Text",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/materials",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Hinweis", "body_md": "Text"},
        ),
    ]


def test_materials_mutations_with_module_id_use_module_endpoints_without_read_resolver(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(201, {}), (200, {}), (204, None), (200, [])])

    assert cli.main(
        [
            "materials",
            "create",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--title",
            "Hinweis",
            "--body-md",
            "Text",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0
    assert cli.main(
        [
            "materials",
            "edit",
            "material-1",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--title",
            "Neu",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0
    assert cli.main(
        [
            "materials",
            "delete",
            "material-1",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--yes",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0
    assert cli.main(
        [
            "materials",
            "reorder",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--ids",
            "material-2",
            "material-1",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0

    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/materials",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Hinweis", "body_md": "Text"},
        ),
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/materials/material-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Neu"},
        ),
        (
            "DELETE",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/materials/material-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        ),
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/materials/reorder",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"material_ids": ["material-2", "material-1"]},
        ),
    ]


def test_materials_upload_with_module_id_uses_module_write_endpoints_without_read_resolver(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    source = tmp_path / "diagramm.pdf"
    payload_bytes = b"%PDF-1.4\nGUSTAV\n"
    source.write_bytes(payload_bytes)
    sha256 = hashlib.sha256(payload_bytes).hexdigest()
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    byte_calls: list[tuple[str, str, dict[str, str] | None, bytes | None]] = []

    def fake_json(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        if url.endswith("/materials/upload-intents"):
            return 200, {
                "intent_id": "intent-1",
                "url": "https://storage.example/upload",
                "headers": {"content-type": "application/pdf"},
            }
        return 201, {"id": "material-1", "title": "Diagramm", "kind": "file"}

    def fake_bytes(method: str, url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None):
        byte_calls.append((method, url, headers, data))
        return 200, b""

    monkeypatch.setattr(cli, "_http_json", fake_json)
    monkeypatch.setattr(cli, "_http_bytes", fake_bytes, raising=False)

    code = cli.main(
        [
            "materials",
            "upload",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--file",
            str(source),
            "--title",
            "Diagramm",
            "--json",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/materials/upload-intents",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"filename": "diagramm.pdf", "mime_type": "application/pdf", "size_bytes": len(payload_bytes)},
        ),
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/materials/finalize",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"intent_id": "intent-1", "title": "Diagramm", "sha256": sha256},
        ),
    ]
    assert byte_calls == [("PUT", "https://storage.example/upload", {"content-type": "application/pdf"}, payload_bytes)]


def test_tasks_create_sends_instruction_and_criteria(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Erkläre den Algorithmus.",
            "--criterion",
            "nennt Eingabe",
            "--criterion",
            "nennt Ausgabe",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"instruction_md": "Erkläre den Algorithmus.", "criteria": ["nennt Eingabe", "nennt Ausgabe"]},
    )


def test_tasks_mutations_with_module_id_use_module_endpoints_without_read_resolver(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(201, {}), (200, {}), (204, None), (200, [])])

    assert cli.main(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--instruction-md",
            "Bearbeite die Aufgabe.",
            "--kind",
            "h5p",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0
    assert cli.main(
        [
            "tasks",
            "edit",
            "task-1",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--instruction-md",
            "Neu",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0
    assert cli.main(
        [
            "tasks",
            "delete",
            "task-1",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--yes",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0
    assert cli.main(
        [
            "tasks",
            "reorder",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--ids",
            "task-2",
            "task-1",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    ) == 0

    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/tasks",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"instruction_md": "Bearbeite die Aufgabe.", "h5p": {"content_id": None, "display_options": {}}},
        ),
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/tasks/task-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"instruction_md": "Neu"},
        ),
        (
            "DELETE",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/tasks/task-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        ),
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/tasks/reorder",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"task_ids": ["task-2", "task-1"]},
        ),
    ]


def test_tasks_create_visual_kind_sends_marker_config(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(201, {"id": "task-1", "kind": "visual"})])

    code = cli.main(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Analysiere das Bild.",
            "--kind",
            "visual",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"instruction_md": "Analysiere das Bild.", "visual": {}},
        )
    ]


def test_materials_upload_uses_intent_put_and_finalize(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    source = tmp_path / "diagramm.pdf"
    payload_bytes = b"%PDF-1.4\nGUSTAV\n"
    source.write_bytes(payload_bytes)
    sha256 = hashlib.sha256(payload_bytes).hexdigest()
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    byte_calls: list[tuple[str, str, dict[str, str] | None, bytes | None]] = []

    def fake_json(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        if url.endswith("/materials/upload-intents"):
            return 200, {
                "intent_id": "intent-1",
                "material_id": "material-1",
                "storage_key": "materials/diagramm.pdf",
                "url": "https://storage.example/upload",
                "headers": {"content-type": "application/pdf", "x-upsert": "false"},
                "accepted_mime_types": ["application/pdf", "image/png", "image/jpeg"],
                "max_size_bytes": 20971520,
                "expires_at": "2026-05-26T10:00:00Z",
            }
        return 201, {"id": "material-1", "title": "Diagramm", "kind": "file"}

    def fake_bytes(method: str, url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None):
        byte_calls.append((method, url, headers, data))
        return 200, b""

    monkeypatch.setattr(cli, "_http_json", fake_json)
    monkeypatch.setattr(cli, "_http_bytes", fake_bytes, raising=False)

    stdout = io.StringIO()
    code = cli.main(
        [
            "materials",
            "upload",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--file",
            str(source),
            "--title",
            "Diagramm",
            "--alt-text",
            "Ablaufdiagramm",
            "--json",
        ],
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(stdout.getvalue())["id"] == "material-1"
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/upload-intents",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"filename": "diagramm.pdf", "mime_type": "application/pdf", "size_bytes": len(payload_bytes)},
        ),
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/finalize",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"intent_id": "intent-1", "title": "Diagramm", "sha256": sha256, "alt_text": "Ablaufdiagramm"},
        ),
    ]
    assert byte_calls == [
        (
            "PUT",
            "https://storage.example/upload",
            {"content-type": "application/pdf", "x-upsert": "false"},
            payload_bytes,
        )
    ]


def test_materials_upload_supports_self_contained_simulations(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    source = tmp_path / "modell.html"
    content = b"<!doctype html><html><body>Modell</body></html>"
    source.write_bytes(content)
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_json(method: str, url: str, *, headers=None, json_body=None):
        calls.append((method, url, headers, json_body))
        if url.endswith("/materials/upload-intents"):
            return 200, {
                "intent_id": "intent-sim",
                "url": "https://storage.example/upload",
                "headers": {"content-type": "text/html"},
            }
        return 201, {"id": "simulation-1", "kind": "simulation"}

    monkeypatch.setattr(cli, "_http_json", fake_json)
    monkeypatch.setattr(cli, "_http_bytes", lambda *args, **kwargs: (200, b""), raising=False)

    code = cli.main(
        [
            "materials", "upload", "--unit-id", "unit-1", "--section-id", "section-1",
            "--file", str(source), "--title", "Modell", "--kind", "simulation",
            "--body-md", "Verändere den Regler.",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0][3] == {
        "kind": "simulation",
        "filename": "modell.html",
        "mime_type": "text/html",
        "size_bytes": len(content),
    }
    assert calls[1][3] == {
        "intent_id": "intent-sim",
        "title": "Modell",
        "sha256": hashlib.sha256(content).hexdigest(),
        "body_md": "Verändere den Regler.",
    }


def test_materials_download_refuses_overwrite_without_force(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    target = tmp_path / "material.pdf"
    target.write_bytes(b"existing")
    calls = _capture_http(monkeypatch)
    monkeypatch.setattr(cli, "_http_bytes", lambda *args, **kwargs: (200, b"new"), raising=False)

    stderr = io.StringIO()
    code = cli.main(
        [
            "materials",
            "download",
            "material-1",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--output",
            str(target),
        ],
        stdout=io.StringIO(),
        stderr=stderr,
    )

    assert code == 1
    assert "--force" in stderr.getvalue()
    assert target.read_bytes() == b"existing"
    assert calls == []


def test_h5p_import_uses_task_scoped_multipart_endpoint(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    h5p_file = tmp_path / "quiz.h5p"
    h5p_file.write_bytes(b"PK\x03\x04demo")
    multipart_calls: list[tuple[str, str, dict[str, str] | None, str, bytes, str]] = []

    def fake_multipart(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        field_name: str,
        filename: str,
        content: bytes,
        content_type: str,
    ):
        multipart_calls.append((method, url, headers, filename, content, content_type))
        return 200, {"id": "task-1", "kind": "h5p"}

    monkeypatch.setattr(cli, "_http_multipart", fake_multipart, raising=False)

    code = cli.main(
        [
            "h5p",
            "import",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--task-id",
            "task-1",
            "--file",
            str(h5p_file),
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert multipart_calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks/task-1/h5p/import",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            "quiz.h5p",
            b"PK\x03\x04demo",
            "application/zip",
        )
    ]


def test_h5p_import_with_module_id_uses_module_write_endpoint_without_read_resolver(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    h5p_file = tmp_path / "quiz.h5p"
    h5p_file.write_bytes(b"PK\x03\x04demo")
    json_calls: list[tuple[str, str]] = []
    multipart_calls: list[tuple[str, str, dict[str, str] | None, str, bytes, str]] = []

    def fake_json(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        json_calls.append((method, url))
        return 500, {"error": "unexpected_read_resolver"}

    def fake_multipart(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        field_name: str,
        filename: str,
        content: bytes,
        content_type: str,
    ):
        multipart_calls.append((method, url, headers, filename, content, content_type))
        return 200, {"id": "task-1", "kind": "h5p"}

    monkeypatch.setattr(cli, "_http_json", fake_json)
    monkeypatch.setattr(cli, "_http_multipart", fake_multipart, raising=False)

    code = cli.main(
        [
            "h5p",
            "import",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--task-id",
            "task-1",
            "--file",
            str(h5p_file),
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert json_calls == []
    assert multipart_calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/tasks/task-1/h5p/import",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            "quiz.h5p",
            b"PK\x03\x04demo",
            "application/zip",
        )
    ]


def test_h5p_reset_with_module_id_uses_module_write_endpoint_without_read_resolver(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, {"id": "task-1", "kind": "h5p"})])

    code = cli.main(
        [
            "h5p",
            "reset",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--task-id",
            "task-1",
            "--yes",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/tasks/task-1/h5p/reset",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        )
    ]


def test_h5p_export_with_module_id_still_resolves_section_target(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    output = tmp_path / "quiz.h5p"
    json_calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_json(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        json_calls.append((method, url, headers, json_body))
        return 200, {"module_id": "module-1", "section_id": "section-hidden"}

    monkeypatch.setattr(cli, "_http_json", fake_json)
    monkeypatch.setattr(cli, "_http_bytes", lambda method, url, *, headers=None, data=None: (200, b"PK\x03\x04demo"))

    code = cli.main(
        [
            "h5p",
            "export",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--task-id",
            "task-1",
            "--output",
            str(output),
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert json_calls == [
        (
            "GET",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/content-target",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        )
    ]
    assert output.read_bytes() == b"PK\x03\x04demo"


def test_units_edit_sends_only_changed_fields(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, {"id": "unit-1", "title": "Neu"})])

    code = cli.main(
        ["units", "edit", "unit-1", "--title", "Neu"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Neu"},
        )
    ]


def test_sections_create_edit_and_delete_use_expected_endpoints(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(201, {}), (200, {}), (204, None)])

    assert cli.main(["sections", "create", "--unit-id", "unit-1", "--title", "A"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["sections", "edit", "section-1", "--unit-id", "unit-1", "--title", "B"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["sections", "delete", "section-1", "--unit-id", "unit-1", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "A"},
        ),
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "B"},
        ),
        (
            "DELETE",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        ),
    ]


def test_phases_list_edit_delete_and_reorder_use_expected_endpoints(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, []), (200, {}), (204, None), (200, [])])

    assert cli.main(["phases", "list", "--unit-id", "unit-1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["phases", "edit", "phase-1", "--unit-id", "unit-1", "--title", "B"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["phases", "delete", "phase-1", "--unit-id", "unit-1", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["phases", "reorder", "--unit-id", "unit-1", "--ids", "phase-2", "phase-1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/phases", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("PATCH", "https://gustav.example/api/teaching/units/unit-1/phases/phase-1", {"Authorization": "Bearer gustav_cli_token_secret"}, {"title": "B"}),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/phases/phase-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("POST", "https://gustav.example/api/teaching/units/unit-1/phases/reorder", {"Authorization": "Bearer gustav_cli_token_secret"}, {"phase_ids": ["phase-2", "phase-1"]}),
    ]


def test_modules_list_edit_delete_and_edge_delete_use_expected_endpoints(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, {"modules": []}), (200, {}), (204, None), (204, None)])

    assert cli.main(["modules", "list", "--unit-id", "unit-1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["modules", "edit", "module-1", "--unit-id", "unit-1", "--title", "B", "--required-prereq-count", "1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["modules", "delete", "module-1", "--unit-id", "unit-1", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["module-edges", "delete", "--unit-id", "unit-1", "--from", "m1", "--to", "m2", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/modules/graph", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("PATCH", "https://gustav.example/api/teaching/units/unit-1/modules/module-1", {"Authorization": "Bearer gustav_cli_token_secret"}, {"title": "B", "required_prereq_count": 1}),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/modules/module-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/modules/m1/edges/m2", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
    ]


def test_materials_list_edit_delete_and_reorder_use_section_endpoint(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, []), (200, {}), (204, None), (200, [])])

    target = ["--unit-id", "unit-1", "--section-id", "section-1"]
    assert cli.main(["materials", "list", *target], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["materials", "edit", "material-1", *target, "--title", "B", "--body-md", "Text", "--alt-text", "Alt"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["materials", "delete", "material-1", *target, "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["materials", "reorder", *target, "--ids", "m2", "m1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("PATCH", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/material-1", {"Authorization": "Bearer gustav_cli_token_secret"}, {"title": "B", "body_md": "Text", "alt_text": "Alt"}),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/material-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("POST", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/reorder", {"Authorization": "Bearer gustav_cli_token_secret"}, {"material_ids": ["m2", "m1"]}),
    ]


def test_tasks_list_edit_delete_and_reorder_use_section_endpoint(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, []), (200, {}), (204, None), (200, [])])

    target = ["--unit-id", "unit-1", "--section-id", "section-1"]
    assert cli.main(["tasks", "list", *target], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["tasks", "edit", "task-1", *target, "--instruction-md", "Neu", "--criterion", "A", "--teacher-context-md", "privat", "--due-at", "2026-05-12T08:00:00Z", "--max-attempts", "2"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["tasks", "delete", "task-1", *target, "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["tasks", "reorder", *target, "--ids", "t2", "t1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks/task-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"instruction_md": "Neu", "criteria": ["A"], "teacher_context_md": "privat", "due_at": "2026-05-12T08:00:00Z", "max_attempts": 2},
        ),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks/task-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("POST", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks/reorder", {"Authorization": "Bearer gustav_cli_token_secret"}, {"task_ids": ["t2", "t1"]}),
    ]


def test_delete_commands_require_yes_before_http_call(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch)

    cases = [
        ["sections", "delete", "section-1", "--unit-id", "unit-1"],
        ["phases", "delete", "phase-1", "--unit-id", "unit-1"],
        ["modules", "delete", "module-1", "--unit-id", "unit-1"],
        ["module-edges", "delete", "--unit-id", "unit-1", "--from", "m1", "--to", "m2"],
        ["materials", "delete", "material-1", "--unit-id", "unit-1", "--section-id", "section-1"],
        ["tasks", "delete", "task-1", "--unit-id", "unit-1", "--section-id", "section-1"],
    ]
    for argv in cases:
        stderr = io.StringIO()
        assert cli.main(argv, stdout=io.StringIO(), stderr=stderr) == 1
        assert "--yes" in stderr.getvalue()

    assert calls == []


def test_module_material_create_reports_write_endpoint_error(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(404, {"error": "not_found"})])

    stderr = io.StringIO()
    code = cli.main(
        ["materials", "create", "--unit-id", "unit-1", "--module-id", "missing", "--title", "A", "--body-md", "Text"],
        stdout=io.StringIO(),
        stderr=stderr,
    )

    assert code == 1
    assert "API-Fehler (404)" in stderr.getvalue()
    assert len(calls) == 1
    assert calls[0][0] == "POST"


def test_api_errors_do_not_leak_configured_token(tmp_path, monkeypatch) -> None:
    token = "gustav_cli_very_secret_token"
    _configure_test_cli(tmp_path, monkeypatch, token=token)
    _capture_http(monkeypatch, [(403, {"error": "forbidden"})])

    stderr = io.StringIO()
    code = cli.main(["units", "list"], stdout=io.StringIO(), stderr=stderr)

    assert code == 1
    assert "API-Fehler (403)" in stderr.getvalue()
    assert token not in stderr.getvalue()
