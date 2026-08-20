"""DB-backed integration between the sync adapter and the real Teaching API."""

from __future__ import annotations

import asyncio
import importlib
from copy import deepcopy
from urllib.parse import urlsplit

import httpx
import pytest
from httpx import ASGITransport

from backend.identity_access.cli_tokens import InMemoryCLITokenStore
from backend.tests.runtime_auth_helpers import install_cli_token_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip
from backend.tools.gustav_cli.config import GustavCLIConfig
from backend.tools.gustav_cli.sync_engine import snapshot_digest
from backend.tools.gustav_cli.sync_remote import GustavSyncClient

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

main = importlib.import_module("backend.web.main")
teaching = importlib.import_module("backend.web.routes.teaching")


@pytest.mark.anyio
async def test_sync_adapter_roundtrips_linear_modular_h5p_and_prune_through_real_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise real auth, routes, repositories, constraints, and DB persistence."""

    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for CLI sync API integration")

    token_store = InMemoryCLITokenStore(now=lambda: 1_000)
    install_cli_token_store(monkeypatch, main, token_store)
    monkeypatch.setattr(
        main.AUTH_WIRING.auth_middleware_dependencies,
        "roles_for_cli_sub",
        lambda sub: ["teacher"],
    )
    created = token_store.create_token(
        user_sub="teacher-cli-sync-api",
        label="Sync integration",
        scopes=["read", "write", "delete"],
        ttl_seconds=3_600,
    )
    headers = {"Authorization": f"Bearer {created.raw_token}"}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="https://test",
    ) as api_client:
        unit_response = await api_client.post(
            "/api/teaching/units",
            headers=headers,
            json={"title": "CLI Sync", "unit_type": "modular"},
        )
        assert unit_response.status_code == 201, unit_response.text
        unit_id = unit_response.json()["id"]
        phases_response = await api_client.get(
            f"/api/teaching/units/{unit_id}/phases",
            headers=headers,
        )
        assert phases_response.status_code == 200, phases_response.text
        phase_id = phases_response.json()[0]["id"]
        linear_response = await api_client.post(
            "/api/teaching/units",
            headers=headers,
            json={"title": "CLI Linear Sync", "unit_type": "linear"},
        )
        assert linear_response.status_code == 201, linear_response.text
        linear_unit_id = linear_response.json()["id"]

        loop = asyncio.get_running_loop()

        def api_request(method, url, *, headers=None, json_body=None):
            parsed = urlsplit(url)
            path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            future = asyncio.run_coroutine_threadsafe(
                api_client.request(method, path, headers=headers, json=json_body),
                loop,
            )
            response = future.result(timeout=20)
            if response.status_code == 204 or not response.content:
                return response.status_code, None
            return response.status_code, response.json()

        monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", api_request)
        sync_client = GustavSyncClient(
            GustavCLIConfig(base_url="https://test", token=created.raw_token)
        )
        mapping = {
            "units": {
                "cli-sync": {
                    "remote_id": unit_id,
                    "phases": {"start": phase_id},
                },
                "cli-linear-sync": {"remote_id": linear_unit_id},
            }
        }
        remote, mapping = await asyncio.to_thread(sync_client.fetch_snapshot, mapping)
        unit = remote["units"]["cli-sync"]
        unit["phases"][0]["key"] = "start"
        mapping["units"]["cli-sync"]["phases"] = {"start": phase_id}
        local = deepcopy(remote)
        local_unit = local["units"]["cli-sync"]
        local_unit["phases"][0]["key"] = "start"
        local_unit["phases"][0]["title"] = "Start"
        local_unit["phases"].append({"key": "entfernen", "title": "Später entfernen"})
        local_unit["modules"] = [
            {
                "key": "quelle",
                "phase": "start",
                "title": "Quelle",
                "module_kind": "learning",
                "required_prereq_count": 0,
                "materials": [],
                "tasks": [],
            },
            {
                "key": "ziel",
                "phase": "start",
                "title": "Ziel",
                "module_kind": "learning",
                "required_prereq_count": 1,
                "materials": [],
                "tasks": [
                    {
                        "key": "quiz-entwurf",
                        "kind": "h5p",
                        "instruction_md": "Konfiguriere das Quiz.",
                        "criteria": [],
                        "teacher_context_md": None,
                        "model_solution_md": None,
                        "due_at": None,
                        "max_attempts": None,
                        "display_options": {},
                        "h5p_sha256": None,
                    }
                ],
            },
            {
                "key": "alt",
                "phase": "entfernen",
                "title": "Zu entfernendes Modul",
                "module_kind": "learning",
                "required_prereq_count": 0,
                "materials": [],
                "tasks": [],
            },
        ]
        local_unit["edges"] = [{"from": "quelle", "to": "ziel"}]
        local_linear = local["units"]["cli-linear-sync"]
        local_linear["sections"] = [
            {
                "key": "einstieg",
                "title": "Einstieg",
                "materials": [
                    {
                        "key": "text",
                        "kind": "markdown",
                        "title": "Einführung",
                        "body_md": "Ein echter API-Rundlauf.",
                    }
                ],
                "tasks": [],
            }
        ]

        mapping = await asyncio.to_thread(
            sync_client.push_snapshot,
            local,
            remote,
            mapping,
            prune=False,
            checkpoint=lambda current: None,
        )
        verified, mapping = await asyncio.to_thread(sync_client.fetch_snapshot, mapping)
        pruned = deepcopy(local)
        pruned_unit = pruned["units"]["cli-sync"]
        pruned_unit["phases"] = [
            phase for phase in pruned_unit["phases"] if phase["key"] != "entfernen"
        ]
        pruned_unit["modules"] = [
            module for module in pruned_unit["modules"] if module["key"] != "alt"
        ]
        mapping = await asyncio.to_thread(
            sync_client.push_snapshot,
            pruned,
            verified,
            mapping,
            prune=True,
            checkpoint=lambda current: None,
        )
        verified, _ = await asyncio.to_thread(sync_client.fetch_snapshot, mapping)

    assert snapshot_digest(verified) == snapshot_digest(pruned)
    verified_unit = verified["units"]["cli-sync"]
    assert verified_unit["edges"] == [{"from": "quelle", "to": "ziel"}]
    assert verified_unit["modules"][1]["required_prereq_count"] == 1
    assert verified_unit["modules"][1]["tasks"][0]["h5p_sha256"] is None
    assert verified["units"]["cli-linear-sync"]["sections"][0]["materials"][0][
        "body_md"
    ] == "Ein echter API-Rundlauf."
