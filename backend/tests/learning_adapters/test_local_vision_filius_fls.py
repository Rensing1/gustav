"""
Local Vision adapter -- Filius FLS extraction (deterministic).

Intent:
    Filius submissions (`application/x.filius.fls`) must not go through OCR.
    The adapter should extract deterministic Markdown evidence instead.
"""

from __future__ import annotations

from hashlib import sha256
import io
from pathlib import Path
import zipfile

import pytest

pytest.importorskip("psycopg")

from backend.learning.workers.process_learning_submission_jobs import VisionResult  # type: ignore
from backend.storage.config import get_submissions_bucket


FILIUS_MIME = "application/x.filius.fls"
XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>2.5</string>
</java>
"""


def _fls_bytes() -> bytes:
    return _fls_bytes_with_config(XML)


def _fls_bytes_with_config(config: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("projekt/konfiguration.xml", config)
    return buf.getvalue()


def test_local_vision_filius_fls_returns_evidence_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fls_bytes = _fls_bytes()
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff01",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)
    assert isinstance(result, VisionResult)
    assert "filius.evidence.v1" in result.text_md
    assert isinstance(result.raw_metadata, dict)
    assert result.raw_metadata.get("backend") == "filius_fls"


def test_local_vision_filius_fls_returns_topology_evidence_for_real_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fls_bytes = Path("backend/tests/fixtures/filius/inf-schule-clientserver/filius_ClientServer.fls").read_bytes()
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff02",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert "## Nodes" in result.text_md
    assert "## Links" in result.text_md
    assert "192.168.0.0/24" in result.text_md
    assert "GUIKnotenItem" in result.text_md


def test_local_vision_filius_fls_returns_routing_evidence_for_real_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fls_bytes = Path("backend/tests/fixtures/filius/inf-schule-mehrere-netze/filius_mehrere_netze.fls").read_bytes()
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff03",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert "- manual_routes:" in result.text_md
    assert 'destination: "192.168.1.0/24"' in result.text_md
    assert 'next_hop_ip: "1.0.0.2"' in result.text_md
    assert 'via_interface: "n2-if1"' in result.text_md
    assert "3.0.0.0/24" in result.text_md


def test_local_vision_filius_fls_returns_dns_web_evidence_for_synthetic_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    xml = Path("backend/tests/fixtures/filius/synthetic-dns-web/configuration.xml").read_bytes()
    fls_bytes = _fls_bytes_with_config(xml)
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff04",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert 'class: "filius.software.dns.DNSServer"' in result.text_md
    assert 'path: "/dns/hosts"' in result.text_md
    assert 'class: "filius.software.www.WebServer"' in result.text_md
    assert 'path: "/webserver/index.html"' in result.text_md
    assert "must not leak" not in result.text_md


def test_local_vision_filius_fls_returns_firewall_evidence_for_official_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fls_bytes = Path(
        "backend/tests/fixtures/filius/filius-official-firewall/"
        "Internet_Komplett_mit_eMail_Webserver_Intranet_Portforwarding_Firewall_DHCP_DE.fls"
    ).read_bytes()
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff05",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert "- firewalls:" in result.text_md
    assert 'activated: "true"' in result.text_md
    assert 'source: "10.10.20.0/24"' in result.text_md
    assert 'destination: "42.0.0.10/32"' in result.text_md
    assert "password" not in result.text_md.lower()
    assert "passwort" not in result.text_md.lower()


def test_local_vision_filius_fls_returns_email_metadata_for_official_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fls_bytes = Path("backend/tests/fixtures/filius/filius-official-email/email_komplett.fls").read_bytes()
    digest = sha256(fls_bytes).hexdigest()

    bucket = get_submissions_bucket()
    submission = {
        "id": "deadbeef-dead-beef-dead-beef0000ff06",
        "kind": "file",
        "text_body": None,
        "course_id": "course-1",
        "task_id": "task-1",
        "student_sub": "student-1",
    }

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(storage_root))

    storage_key = f"{bucket}/{submission['course_id']}/{submission['task_id']}/{submission['student_sub']}/project.fls"
    file_path = storage_root / storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(fls_bytes)

    job_payload = {
        "mime_type": FILIUS_MIME,
        "storage_key": storage_key,
        "size_bytes": file_path.stat().st_size,
        "sha256": digest,
    }

    import importlib

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    result: VisionResult = adapter.extract(submission=submission, job_payload=job_payload)

    assert "- email_clients:" in result.text_md
    assert "- email_servers:" in result.text_md
    assert 'mail_domain: "senior.de"' in result.text_md
    assert 'email: "rechner3@senior.de"' in result.text_md
    assert "password" not in result.text_md.lower()
    assert "passwort" not in result.text_md.lower()
    assert "subject:" not in result.text_md.lower()
