from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.tools.local_ca_trust import (
    CERTIFICATE_NICKNAME,
    LocalCATrustManager,
    TrustError,
    certificate_fingerprint,
)


class FakeRunner:
    """Simulate Docker, sudo and NSS while delegating certificate checks to OpenSSL."""

    def __init__(self, caddy_certificate: bytes, *, docker_returncode: int = 0) -> None:
        self.caddy_certificate = caddy_certificate
        self.docker_returncode = docker_returncode
        self.commands: list[tuple[str, ...]] = []
        self.nss_certificates: dict[Path, dict[str, bytes]] = {}

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
        command = tuple(str(part) for part in args)
        self.commands.append(command)

        if command[:3] == ("docker", "exec", "gustav-caddy"):
            return subprocess.CompletedProcess(
                args,
                self.docker_returncode,
                stdout=self.caddy_certificate if self.docker_returncode == 0 else b"",
                stderr=b"Caddy is unavailable" if self.docker_returncode else b"",
            )

        if command[0] == "openssl":
            return subprocess.run(args, capture_output=True, check=False)

        if command[:2] == ("sudo", "install"):
            source = Path(command[-2])
            destination = Path(command[-1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

        if command[:2] == ("sudo", "update-ca-certificates"):
            return subprocess.CompletedProcess(args, 0, stdout=b"updated", stderr=b"")

        if command[0] == "certutil":
            database = Path(command[command.index("-d") + 1].removeprefix("sql:"))
            entries = self.nss_certificates.setdefault(database, {})
            if "-N" in command:
                database.mkdir(parents=True, exist_ok=True)
                (database / "cert9.db").touch()
                return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")
            nickname = command[command.index("-n") + 1]
            if "-L" in command:
                certificate = entries.get(nickname)
                return subprocess.CompletedProcess(
                    args,
                    0 if certificate else 255,
                    stdout=certificate or b"",
                    stderr=b"" if certificate else b"not found",
                )
            if "-D" in command:
                entries.pop(nickname, None)
                return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")
            if "-A" in command:
                certificate_path = Path(command[command.index("-i") + 1])
                entries[nickname] = certificate_path.read_bytes()
                database.mkdir(parents=True, exist_ok=True)
                (database / "cert9.db").touch()
                return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

        raise AssertionError(f"Unexpected command: {command}")

    def mutations(self) -> list[tuple[str, ...]]:
        return [
            command
            for command in self.commands
            if command[:2] == ("sudo", "install")
            or command[:2] == ("sudo", "update-ca-certificates")
            or (
                command
                and command[0] == "certutil"
                and any(flag in command for flag in ("-N", "-A", "-D"))
            )
        ]


@pytest.fixture
def ca_certificate(tmp_path: Path) -> bytes:
    certificate = tmp_path / "root.crt"
    private_key = tmp_path / "root.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
            "-subj",
            "/CN=GUSTAV test CA",
            "-days",
            "1",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
        ],
        check=True,
        capture_output=True,
    )
    return certificate.read_bytes()


@pytest.fixture
def second_ca_certificate(tmp_path: Path) -> bytes:
    certificate = tmp_path / "other-root.crt"
    private_key = tmp_path / "other-root.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
            "-subj",
            "/CN=Old GUSTAV test CA",
            "-days",
            "1",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
        ],
        check=True,
        capture_output=True,
    )
    return certificate.read_bytes()


@pytest.fixture
def non_ca_certificate(tmp_path: Path) -> bytes:
    certificate = tmp_path / "leaf.crt"
    private_key = tmp_path / "leaf.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
            "-subj",
            "/CN=Not a CA",
            "-days",
            "1",
            "-addext",
            "basicConstraints=critical,CA:FALSE",
        ],
        check=True,
        capture_output=True,
    )
    return certificate.read_bytes()


def _create_default_firefox_profile(home: Path, relative_root: Path) -> Path:
    firefox_root = home / relative_root
    profile = firefox_root / "test.default"
    profile.mkdir(parents=True)
    (profile / "cert9.db").touch()
    (firefox_root / "profiles.ini").write_text(
        "[Profile0]\nName=default\nIsRelative=1\nPath=test.default\nDefault=1\n",
        encoding="utf-8",
    )
    return profile


def _manager(
    tmp_path: Path,
    runner: FakeRunner,
    *,
    certutil_path: str | None = "/usr/bin/certutil",
    with_firefox: bool = True,
) -> tuple[LocalCATrustManager, Path, Path, Path | None]:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    system_ca = tmp_path / "system" / "gustav-caddy-local.crt"
    repo_root.mkdir()
    home.mkdir()
    chromium_database = home / ".pki" / "nssdb"
    chromium_database.mkdir(parents=True)
    (chromium_database / "cert9.db").touch()
    firefox_profile = None
    if with_firefox:
        firefox_profile = _create_default_firefox_profile(
            home, Path("snap/firefox/common/.mozilla/firefox")
        )

    manager = LocalCATrustManager(
        repo_root=repo_root,
        home=home,
        system_ca_path=system_ca,
        runner=runner,
        which=lambda name: certutil_path if name == "certutil" else f"/usr/bin/{name}",
    )
    return manager, system_ca, chromium_database, firefox_profile


def test_trust_installs_valid_current_ca_in_all_discovered_stores(
    tmp_path: Path, ca_certificate: bytes
) -> None:
    runner = FakeRunner(ca_certificate)
    manager, system_ca, chromium_database, firefox_profile = _manager(tmp_path, runner)

    report = manager.trust()

    expected = certificate_fingerprint(ca_certificate)
    assert certificate_fingerprint(system_ca.read_bytes()) == expected
    chromium_certificate = runner.nss_certificates[chromium_database][CERTIFICATE_NICKNAME]
    assert certificate_fingerprint(chromium_certificate) == expected
    assert firefox_profile is not None
    firefox_certificate = runner.nss_certificates[firefox_profile][CERTIFICATE_NICKNAME]
    assert certificate_fingerprint(firefox_certificate) == expected
    assert set(report.changed) == {"system", "chromium/codex", "firefox:snap:test.default"}
    assert (manager.export_path).read_bytes() == ca_certificate


def test_trust_is_idempotent_for_matching_fingerprints(
    tmp_path: Path, ca_certificate: bytes
) -> None:
    runner = FakeRunner(ca_certificate)
    manager, _, _, _ = _manager(tmp_path, runner)
    manager.trust()
    runner.commands.clear()

    report = manager.trust()

    assert report.changed == []
    assert runner.mutations() == []


def test_status_reports_stale_trust_store(
    tmp_path: Path, ca_certificate: bytes, second_ca_certificate: bytes
) -> None:
    runner = FakeRunner(ca_certificate)
    manager, system_ca, chromium_database, firefox_profile = _manager(tmp_path, runner)
    system_ca.parent.mkdir(parents=True)
    system_ca.write_bytes(second_ca_certificate)
    runner.nss_certificates[chromium_database] = {CERTIFICATE_NICKNAME: second_ca_certificate}
    assert firefox_profile is not None
    runner.nss_certificates[firefox_profile] = {CERTIFICATE_NICKNAME: ca_certificate}

    report = manager.status()
    states = {item.name: item.state for item in report.stores}

    assert states == {
        "system": "stale",
        "chromium/codex": "stale",
        "firefox:snap:test.default": "trusted",
    }
    assert report.is_trusted is False
    assert runner.mutations() == []


def test_trust_replaces_only_stale_gustav_entries(
    tmp_path: Path, ca_certificate: bytes, second_ca_certificate: bytes
) -> None:
    runner = FakeRunner(ca_certificate)
    manager, system_ca, chromium_database, firefox_profile = _manager(tmp_path, runner)
    system_ca.parent.mkdir(parents=True)
    system_ca.write_bytes(second_ca_certificate)
    runner.nss_certificates[chromium_database] = {
        CERTIFICATE_NICKNAME: second_ca_certificate,
        "Unrelated CA": second_ca_certificate,
    }
    assert firefox_profile is not None
    runner.nss_certificates[firefox_profile] = {CERTIFICATE_NICKNAME: second_ca_certificate}

    manager.trust()

    assert "Unrelated CA" in runner.nss_certificates[chromium_database]
    assert all(
        command[command.index("-n") + 1] == CERTIFICATE_NICKNAME
        for command in runner.commands
        if command and command[0] == "certutil" and "-D" in command
    )


def test_export_failure_does_not_change_trust_stores(tmp_path: Path, ca_certificate: bytes) -> None:
    runner = FakeRunner(ca_certificate, docker_returncode=1)
    manager, _, _, _ = _manager(tmp_path, runner)

    with pytest.raises(TrustError, match="Caddy"):
        manager.trust()

    assert runner.mutations() == []
    assert not manager.export_path.exists()


def test_invalid_certificate_does_not_change_trust_stores(tmp_path: Path) -> None:
    runner = FakeRunner(b"not a certificate")
    manager, _, _, _ = _manager(tmp_path, runner)

    with pytest.raises(TrustError, match="Zertifikat"):
        manager.trust()

    assert runner.mutations() == []


def test_non_ca_certificate_does_not_change_trust_stores(
    tmp_path: Path, non_ca_certificate: bytes
) -> None:
    runner = FakeRunner(non_ca_certificate)
    manager, _, _, _ = _manager(tmp_path, runner)

    with pytest.raises(TrustError, match="Root-CA-Zertifikat"):
        manager.trust()

    assert runner.mutations() == []


def test_missing_certutil_reports_package_hint_before_changes(
    tmp_path: Path, ca_certificate: bytes
) -> None:
    runner = FakeRunner(ca_certificate)
    manager, _, _, _ = _manager(tmp_path, runner, certutil_path=None)

    with pytest.raises(TrustError, match="libnss3-tools"):
        manager.trust()

    assert runner.mutations() == []


def test_missing_firefox_profile_is_reported_without_guessing(
    tmp_path: Path, ca_certificate: bytes
) -> None:
    runner = FakeRunner(ca_certificate)
    manager, _, _, _ = _manager(tmp_path, runner, with_firefox=False)

    with pytest.raises(TrustError, match="Firefox"):
        manager.trust()

    assert runner.mutations() == []
