"""Explicit material reads preserve authorization, bytes and nonblocking adapters."""

import asyncio
import importlib
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from backend.web.learning_material_providers import LearningMaterialProviders
from backend.web.main import create_app
from backend.web.material_file_access import (
    MaterialVisibilityLookupUnavailable,
    StudentMaterialAssetMetadata,
    StudentMaterialFileMetadata,
)
from backend.web.simulation_player import SIMULATION_CONTENT_SECURITY_POLICY

pytestmark = pytest.mark.anyio("asyncio")
COURSE, SECTION, MATERIAL, UNIT = (str(uuid4()) for _ in range(4))
FILE_PATH = f"/api/learning/courses/{COURSE}/materials/{MATERIAL}/file"
SIM_PATH = f"/api/learning/courses/{COURSE}/materials/{MATERIAL}/simulation"
ALIAS_PATH = f"/api/learning/courses/{COURSE}/sections/{SECTION}/materials/{MATERIAL}/file"
FILE = StudentMaterialFileMetadata(
    MATERIAL, SECTION, UNIT, "application/pdf", 12, "private/key", 'blatt"\r\n.pdf'
)
SIM = StudentMaterialAssetMetadata(
    MATERIAL, SECTION, UNIT, "simulation", "text/html", 12, "private/sim", "sim.html"
)


def client_for(providers, role="student"):
    app = create_app(
        learning_material_providers=providers,
        access_token_verifier=lambda token, cfg: {
            "sub": "learner",
            "realm_access": {"roles": [role]},
        },
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test.jwt"},
    )


def providers_for(label="A", *, storage=None, download=None):
    def presign(**kwargs):
        assert kwargs["expires_in"] == 60
        return {"url": f"https://storage.example/{label}", "headers": {"authorization": label}}

    async def fetch(**kwargs):
        assert kwargs["url"] == f"https://storage.example/{label}"
        assert kwargs["headers"] == {"authorization": label}
        assert kwargs["max_bytes"] >= 12
        return label.encode()

    return LearningMaterialProviders(
        repository=lambda: label,
        storage=storage or (lambda: SimpleNamespace(presign_download=presign)),
        download=download or fetch,
    )


@pytest.fixture
def metadata(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_material_providers")
    calls = []

    def read(kind, **kwargs):
        assert kwargs["student_sub"] == "learner"
        assert (kwargs["course_id"], kwargs["material_id"]) == (COURSE, MATERIAL)
        calls.append((kwargs["repo"], kind))
        return FILE if kind == "file" else SIM

    monkeypatch.setattr(
        wiring, "load_student_material_file_metadata", lambda **kw: read("file", **kw)
    )
    monkeypatch.setattr(
        wiring, "load_student_material_asset_metadata", lambda **kw: read("simulation", **kw)
    )
    return calls


@pytest.mark.parametrize("path", [FILE_PATH, ALIAS_PATH, SIM_PATH])
async def test_interleaved_material_reads_are_isolated(metadata, path):
    async with client_for(providers_for("A")) as a, client_for(providers_for("B")) as b:
        for client, label in [(a, "A"), (b, "B"), (a, "A")]:
            response = await client.get(path)
            assert response.status_code == 200
            assert response.content == label.encode()
            assert response.headers["cache-control"] == "private, no-store"
            assert "private/" not in str(response.headers)
            if path == SIM_PATH:
                assert (
                    response.headers["content-security-policy"]
                    == SIMULATION_CONTENT_SECURITY_POLICY
                )
                assert response.headers["x-content-type-options"] == "nosniff"
            else:
                assert response.headers["content-disposition"] == 'inline; filename="blatt.pdf"'
                assert response.headers["vary"] == "Origin"
    assert [label for label, _ in metadata] == (
        ["A", "A", "B", "B", "A", "A"] if path == ALIAS_PATH else ["A", "B", "A"]
    )


@pytest.mark.parametrize("path", [FILE_PATH, ALIAS_PATH, SIM_PATH])
@pytest.mark.parametrize("role", ["teacher", "admin", None])
async def test_denied_identity_never_builds_dependencies(path, role):
    def forbidden():
        pytest.fail("unauthorized dependency access")

    providers = replace(providers_for(), repository=forbidden, storage=forbidden)
    async with client_for(providers, role or "student") as client:
        if role is None:
            client.headers.clear()
        response = await client.get(path)
        assert response.status_code == (401 if role is None else 403)
        assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("path", [FILE_PATH, ALIAS_PATH, SIM_PATH])
async def test_invalid_ids_precede_dependencies(path):
    def forbidden():
        pytest.fail("invalid ID reached repository")

    async with client_for(replace(providers_for(), repository=forbidden)) as client:
        response = await client.get(path.replace(MATERIAL, "invalid"))
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_uuid"
        client.headers.clear()
        response = await client.get(path.replace(MATERIAL, "invalid"))
        # The authentication middleware rejects before either HTTP handler runs.
        assert response.status_code == 401


@pytest.mark.parametrize("path", [FILE_PATH, ALIAS_PATH])
async def test_disposition_order_and_normalization(metadata, path):
    async with client_for(providers_for()) as client:
        response = await client.get(path, params={"disposition": "bad"})
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_disposition"
        assert len(metadata) == (1 if path == ALIAS_PATH else 0)
        response = await client.get(path, params={"disposition": " ATTACHMENT "})
        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize("path", [FILE_PATH, ALIAS_PATH, SIM_PATH])
@pytest.mark.parametrize("case", ["hidden", "unavailable", "wrong_type"])
async def test_visibility_denial_never_signs(monkeypatch, path, case):
    wiring = importlib.import_module("backend.web.learning_material_providers")

    def read(**kwargs):
        if case == "unavailable":
            raise MaterialVisibilityLookupUnavailable("private DB details")
        if case == "wrong_type" and path == SIM_PATH:
            return replace(SIM, kind="file")
        return None

    monkeypatch.setattr(wiring, "load_student_material_file_metadata", read)
    monkeypatch.setattr(wiring, "load_student_material_asset_metadata", read)

    def forbidden():
        pytest.fail("denied visibility reached storage")

    async with client_for(providers_for(storage=forbidden)) as client:
        response = await client.get(path)
        assert response.status_code == (503 if case == "unavailable" else 404)
        if case == "unavailable":
            assert response.json()["detail"] == "authorization_unavailable"
        assert "private" not in response.text


@pytest.mark.parametrize("case", ["wrong_section", "revoked"])
async def test_alias_checks_section_and_rechecks_visibility(monkeypatch, case):
    wiring = importlib.import_module("backend.web.learning_material_providers")
    rows = iter(
        [replace(FILE, section_id=str(uuid4()))] if case == "wrong_section" else [FILE, None]
    )
    monkeypatch.setattr(wiring, "load_student_material_file_metadata", lambda **kw: next(rows))

    def forbidden():
        pytest.fail("denied alias reached storage")

    async with client_for(providers_for(storage=forbidden)) as client:
        assert (await client.get(ALIAS_PATH)).status_code == 404


@pytest.mark.parametrize("path", [FILE_PATH, SIM_PATH])
@pytest.mark.parametrize("case", ["sign_error", "empty_url", "no_storage", "no_bytes"])
async def test_storage_failures_are_private_503(metadata, path, case):
    def presign(**kwargs):
        if case == "sign_error":
            raise RuntimeError("private signing details")
        return {"url": "" if case == "empty_url" else "https://storage.example/A"}

    async def fetch(**kwargs):
        assert case == "no_bytes"
        return None

    async with client_for(
        providers_for(
            storage=lambda: (
                None if case == "no_storage" else SimpleNamespace(presign_download=presign)
            ),
            download=fetch,
        )
    ) as client:
        response = await client.get(path)
        assert response.status_code == 503
        assert response.json() == {"error": "service_unavailable"}
        assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("phase", ["repository", "storage", "sign"])
async def test_slow_synchronous_dependencies_leave_shell_responsive(metadata, phase):
    started, release = threading.Event(), threading.Event()

    def wait():
        started.set()
        assert release.wait(5)

    providers = providers_for()
    if phase == "repository":
        providers = replace(providers, repository=lambda: (wait(), "A")[1])
    else:

        def presign(**kwargs):
            if phase == "sign":
                wait()
            return {"url": "https://storage.example/A", "headers": {"authorization": "A"}}

        def storage():
            if phase == "storage":
                wait()
            return SimpleNamespace(presign_download=presign)

        providers = replace(providers, storage=storage)
    async with client_for(providers) as client:
        pending = asyncio.create_task(client.get(FILE_PATH))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert (
                await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            ).status_code == 200
        finally:
            release.set()
            response = await pending
        assert response.status_code == 200


def test_material_routes_have_no_dynamic_facade():
    route = importlib.import_module("backend.web.routes.learning_material_file_routes")
    source = Path(route.__file__).read_text()
    assert "_learning_module" not in source and "__import__" not in source
    learning = importlib.import_module("backend.web.routes.learning")
    assert not hasattr(learning, "get_material_file")
    assert not hasattr(learning, "get_material_file_legacy_alias")
    assert not hasattr(learning, "_teaching_storage_adapter")


async def test_default_providers_are_lazy_retryable_and_keep_environment_explicit(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_material_providers")
    calls = {"repo": 0, "storage": 0}
    environment = ["prod"]

    def build(kind):
        calls[kind] += 1
        if calls[kind] == 1:
            raise RuntimeError("temporarily unavailable")
        return object()

    monkeypatch.setattr(wiring, "DBLearningRepo", lambda: build("repo"))
    monkeypatch.setattr(wiring, "_build_storage_adapter", lambda: build("storage"))

    async def download(**kwargs):
        assert kwargs["environment"] == environment[0]
        return b"checked"

    monkeypatch.setattr(wiring, "download_bytes_with_limit", download)
    providers = wiring.create_learning_material_providers(environment=lambda: environment[0])
    assert calls == {"repo": 0, "storage": 0}
    for factory in (providers.repository, providers.storage):
        with pytest.raises(RuntimeError):
            factory()
        assert factory() is factory()
    assert calls == {"repo": 2, "storage": 2}
    for env in ("prod", "test"):
        environment[0] = env
        assert (
            await providers.download(url="https://storage.example/file", max_bytes=12, headers={})
            == b"checked"
        )


def test_storage_builder_uses_standard_configuration_without_route_wiring(monkeypatch):
    wiring = importlib.import_module("backend.web.learning_material_providers")
    storage3 = importlib.import_module("storage3._sync.client")
    adapter_module = importlib.import_module("backend.teaching.storage_supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://storage.example/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    client = object()

    def construct(url, headers):
        assert url == "https://storage.example/storage/v1"
        assert headers == {"Authorization": "Bearer test-service-key", "apikey": "test-service-key"}
        return client

    monkeypatch.setattr(storage3, "SyncStorageClient", construct)
    monkeypatch.setattr(adapter_module, "SupabaseStorageAdapter", lambda value: value)
    assert wiring._build_storage_adapter() is client
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY")
    with pytest.raises(RuntimeError, match="storage_not_configured"):
        wiring._build_storage_adapter()
