"""Manage trust for the public root CA used by GUSTAV's local Caddy proxy.

Why:
    Linux system clients, Chromium/Electron and Firefox can use different trust
    stores. This helper verifies Caddy's public root certificate before placing
    it in those stores, so local HTTPS remains strict without hidden browser
    exceptions.

Permissions:
    Status and export need Docker access. Trust installation additionally needs
    permission to update the current user's NSS databases and uses ``sudo`` for
    the system trust store. It never reads or exports Caddy's private key.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

CADDY_CONTAINER = "gustav-caddy"
CADDY_ROOT_PATH = "/data/caddy/pki/authorities/local/root.crt"
CERTIFICATE_NICKNAME = "GUSTAV Caddy Local CA"
DEFAULT_SYSTEM_CA_PATH = Path("/usr/local/share/ca-certificates/gustav-caddy-local.crt")

Runner = Callable[[list[str]], subprocess.CompletedProcess[bytes]]
Which = Callable[[str], str | None]


class TrustError(RuntimeError):
    """Describe a safe, actionable local CA trust failure."""


@dataclass(frozen=True)
class FirefoxProfile:
    """Identify one active Firefox profile and its installation variant."""

    variant: str
    path: Path

    @property
    def label(self) -> str:
        """Return a stable user-facing label for status output."""
        return f"firefox:{self.variant}:{self.path.name}"


@dataclass(frozen=True)
class StoreStatus:
    """Report whether one trust store contains the current Caddy root CA."""

    name: str
    state: str
    fingerprint: str | None = None


@dataclass(frozen=True)
class StatusReport:
    """Collect the current Caddy fingerprint and all discovered store states."""

    expected_fingerprint: str
    stores: list[StoreStatus]

    @property
    def is_trusted(self) -> bool:
        """Return True only when every discovered store trusts the current CA."""
        return bool(self.stores) and all(store.state == "trusted" for store in self.stores)


@dataclass
class TrustReport:
    """List trust stores changed by one explicit installation run."""

    fingerprint: str
    changed: list[str] = field(default_factory=list)


def _run_command(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run one local command without interpreting its output as shell syntax."""
    return subprocess.run(args, capture_output=True, check=False)


def certificate_fingerprint(pem: bytes) -> str:
    """Return a normalized SHA-256 fingerprint for one PEM certificate."""
    try:
        der = ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TrustError("Die exportierte Datei ist kein gültiges PEM-Zertifikat.") from exc
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[index : index + 2] for index in range(0, len(digest), 2))


class LocalCATrustManager:
    """Inspect, export and explicitly install GUSTAV's current local root CA."""

    def __init__(
        self,
        *,
        repo_root: Path,
        home: Path,
        system_ca_path: Path = DEFAULT_SYSTEM_CA_PATH,
        runner: Runner = _run_command,
        which: Which = shutil.which,
    ) -> None:
        self.repo_root = repo_root
        self.home = home
        self.system_ca_path = system_ca_path
        self.runner = runner
        self.which = which
        self.export_path = repo_root / ".tmp" / "caddy-root.crt"

    def _read_caddy_certificate(self) -> bytes:
        """Read only Caddy's public root certificate through Docker stdout."""
        result = self.runner(["docker", "exec", CADDY_CONTAINER, "cat", CADDY_ROOT_PATH])
        if result.returncode != 0 or not result.stdout.strip():
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            suffix = f" ({detail})" if detail else ""
            raise TrustError(
                "Caddys lokale Root-CA konnte nicht gelesen werden. "
                "Führe zuerst `make up` aus" + suffix + "."
            )
        return result.stdout

    def _validate_certificate_file(self, certificate_path: Path) -> str:
        """Validate PEM shape, validity period and CA basic constraints."""
        pem = certificate_path.read_bytes()
        if not pem.strip():
            raise TrustError("Das exportierte Zertifikat ist leer.")
        fingerprint = certificate_fingerprint(pem)

        validity = self.runner(
            [
                "openssl",
                "verify",
                "-CAfile",
                str(certificate_path),
                str(certificate_path),
            ]
        )
        if validity.returncode != 0:
            raise TrustError(
                "Das exportierte Zertifikat ist ungültig, abgelaufen oder noch nicht gültig."
            )

        constraints = self.runner(
            [
                "openssl",
                "x509",
                "-in",
                str(certificate_path),
                "-noout",
                "-ext",
                "basicConstraints",
            ]
        )
        constraint_text = constraints.stdout.decode("utf-8", errors="replace").replace(" ", "")
        if constraints.returncode != 0 or "CA:TRUE" not in constraint_text:
            raise TrustError("Das exportierte Zertifikat ist kein Root-CA-Zertifikat.")
        return fingerprint

    def _validate_certificate_bytes(self, pem: bytes) -> str:
        """Validate certificate bytes without changing repository state."""
        with tempfile.NamedTemporaryFile(prefix="gustav-caddy-root-", suffix=".crt") as candidate:
            candidate.write(pem)
            candidate.flush()
            return self._validate_certificate_file(Path(candidate.name))

    def export_current_ca(self) -> str:
        """Atomically export and validate Caddy's current public root CA."""
        pem = self._read_caddy_certificate()
        self.export_path.parent.mkdir(parents=True, exist_ok=True)
        candidate = self.export_path.with_name(f"{self.export_path.name}.next")
        try:
            candidate.write_bytes(pem)
            candidate.chmod(0o600)
            fingerprint = self._validate_certificate_file(candidate)
            os.replace(candidate, self.export_path)
        finally:
            candidate.unlink(missing_ok=True)
        return fingerprint

    def chromium_database(self) -> Path:
        """Select Chromium's documented Linux NSS database location."""
        legacy = self.home / ".pki" / "nssdb"
        if legacy.exists():
            return legacy
        return self.home / ".local" / "share" / "pki" / "nssdb"

    def discover_firefox_profiles(self) -> list[FirefoxProfile]:
        """Discover active classic, Snap and Flatpak Firefox profiles."""
        roots = [
            ("classic", self.home / ".mozilla" / "firefox"),
            ("snap", self.home / "snap" / "firefox" / "common" / ".mozilla" / "firefox"),
            (
                "flatpak",
                self.home
                / ".var"
                / "app"
                / "org.mozilla.firefox"
                / ".mozilla"
                / "firefox",
            ),
        ]
        profiles: list[FirefoxProfile] = []
        for variant, root in roots:
            profiles.extend(self._profiles_from_ini(variant, root))
        return profiles

    @staticmethod
    def _profiles_from_ini(variant: str, root: Path) -> list[FirefoxProfile]:
        """Resolve profiles marked as default in one Firefox profiles.ini."""
        profiles_ini = root / "profiles.ini"
        if not profiles_ini.is_file():
            return []
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(profiles_ini, encoding="utf-8")
        except (configparser.Error, OSError):
            return []

        profiles: list[FirefoxProfile] = []
        for section in parser.sections():
            if (
                not section.startswith("Profile")
                or parser.get(section, "Default", fallback="0") != "1"
            ):
                continue
            configured_path = parser.get(section, "Path", fallback="").strip()
            if not configured_path:
                continue
            is_relative = parser.get(section, "IsRelative", fallback="1") == "1"
            profile_path = root / configured_path if is_relative else Path(configured_path)
            if profile_path.is_dir():
                profiles.append(FirefoxProfile(variant=variant, path=profile_path))
        return profiles

    def _nss_fingerprint(self, database: Path) -> str | None:
        """Read the managed GUSTAV certificate from one NSS database."""
        if not (database / "cert9.db").is_file() or self.which("certutil") is None:
            return None
        result = self.runner(
            [
                "certutil",
                "-L",
                "-d",
                f"sql:{database}",
                "-n",
                CERTIFICATE_NICKNAME,
                "-a",
            ]
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        try:
            return certificate_fingerprint(result.stdout)
        except TrustError:
            return None

    @staticmethod
    def _store_state(current: str | None, expected: str) -> str:
        """Classify a trust store fingerprint against the current CA."""
        if current is None:
            return "missing"
        return "trusted" if current == expected else "stale"

    def _source_certificate(self) -> tuple[bytes, str]:
        """Read and validate Caddy's source without persisting it."""
        pem = self._read_caddy_certificate()
        return pem, self._validate_certificate_bytes(pem)

    def status(self) -> StatusReport:
        """Inspect all known trust stores without modifying them."""
        _, expected = self._source_certificate()
        stores: list[StoreStatus] = []

        system_fingerprint = self._file_fingerprint(self.system_ca_path)
        stores.append(
            StoreStatus(
                name="system",
                state=self._store_state(system_fingerprint, expected),
                fingerprint=system_fingerprint,
            )
        )

        chromium_fingerprint = self._nss_fingerprint(self.chromium_database())
        stores.append(
            StoreStatus(
                name="chromium/codex",
                state=self._store_state(chromium_fingerprint, expected),
                fingerprint=chromium_fingerprint,
            )
        )

        for profile in self.discover_firefox_profiles():
            fingerprint = self._nss_fingerprint(profile.path)
            stores.append(
                StoreStatus(
                    name=profile.label,
                    state=self._store_state(fingerprint, expected),
                    fingerprint=fingerprint,
                )
            )
        return StatusReport(expected_fingerprint=expected, stores=stores)

    @staticmethod
    def _file_fingerprint(path: Path) -> str | None:
        """Read a PEM fingerprint, treating missing or malformed files as absent."""
        try:
            return certificate_fingerprint(path.read_bytes())
        except (OSError, TrustError):
            return None

    def _ensure_nss_database(self, database: Path) -> None:
        """Initialize an NSS database only when no database exists yet."""
        if (database / "cert9.db").is_file():
            return
        database.mkdir(parents=True, exist_ok=True)
        result = self.runner(
            ["certutil", "-N", "-d", f"sql:{database}", "--empty-password"]
        )
        if result.returncode != 0:
            raise TrustError(f"Die NSS-Datenbank konnte nicht initialisiert werden: {database}")

    def _replace_nss_certificate(self, database: Path, expected: str) -> bool:
        """Replace only the fixed GUSTAV entry when its fingerprint is stale."""
        self._ensure_nss_database(database)
        current = self._nss_fingerprint(database)
        if current == expected:
            return False
        if current is not None:
            delete = self.runner(
                [
                    "certutil",
                    "-D",
                    "-d",
                    f"sql:{database}",
                    "-n",
                    CERTIFICATE_NICKNAME,
                ]
            )
            if delete.returncode != 0:
                raise TrustError(
                    f"Das veraltete GUSTAV-Zertifikat konnte nicht entfernt werden: {database}"
                )

        add = self.runner(
            [
                "certutil",
                "-A",
                "-d",
                f"sql:{database}",
                "-t",
                "C,,",
                "-n",
                CERTIFICATE_NICKNAME,
                "-i",
                str(self.export_path),
            ]
        )
        if add.returncode != 0 or self._nss_fingerprint(database) != expected:
            raise TrustError(
                f"Das GUSTAV-Zertifikat konnte nach dem Import nicht verifiziert werden: {database}"
            )
        return True

    def _install_system_certificate(self, expected: str) -> bool:
        """Install the public CA into the Linux system store through visible sudo calls."""
        if self._file_fingerprint(self.system_ca_path) == expected:
            return False
        install = self.runner(
            [
                "sudo",
                "install",
                "-m",
                "0644",
                str(self.export_path),
                str(self.system_ca_path),
            ]
        )
        if install.returncode != 0:
            raise TrustError("Die System-CA-Datei konnte mit sudo nicht installiert werden.")
        update = self.runner(["sudo", "update-ca-certificates"])
        if update.returncode != 0 or self._file_fingerprint(self.system_ca_path) != expected:
            raise TrustError(
                "Der Linux-System-Vertrauensspeicher konnte nicht aktualisiert oder geprüft werden."
            )
        return True

    def trust(self) -> TrustReport:
        """Explicitly install the current verified Caddy root in all required stores."""
        if self.which("certutil") is None:
            raise TrustError(
                "`certutil` wird benötigt. Installiere zuerst das Ubuntu-Paket `libnss3-tools`."
            )
        if self.which("openssl") is None:
            raise TrustError("`openssl` wird benötigt, bevor die lokale CA geprüft werden kann.")

        firefox_profiles = self.discover_firefox_profiles()
        if not firefox_profiles:
            raise TrustError(
                "In den klassischen, Snap- oder Flatpak-Pfaden wurde kein aktives "
                "Firefox-Profil gefunden."
            )

        expected = self.export_current_ca()
        report = TrustReport(fingerprint=expected)
        if self._install_system_certificate(expected):
            report.changed.append("system")

        chromium_database = self.chromium_database()
        if self._replace_nss_certificate(chromium_database, expected):
            report.changed.append("chromium/codex")

        for profile in firefox_profiles:
            if self._replace_nss_certificate(profile.path, expected):
                report.changed.append(profile.label)
        return report


def _print_status(report: StatusReport, *, out: TextIO) -> None:
    """Render a compact German status report for developers."""
    state_labels = {"trusted": "vertraut", "stale": "veraltet", "missing": "fehlt"}
    print(f"Aktuelle Caddy-CA: {report.expected_fingerprint}", file=out)
    for store in report.stores:
        detail = f" ({store.fingerprint})" if store.fingerprint else ""
        print(f"- {store.name}: {state_labels.get(store.state, store.state)}{detail}", file=out)


def _build_parser() -> argparse.ArgumentParser:
    """Build the small command-line interface used by Make targets."""
    parser = argparse.ArgumentParser(
        description="Caddys öffentliche lokale Root-CA sicher exportieren und verwalten."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "export", help="Caddys aktuelle öffentliche Root-CA exportieren und prüfen"
    )
    status = subparsers.add_parser(
        "status", help="System- und Browser-Vertrauensspeicher prüfen"
    )
    status.add_argument(
        "--warn-only",
        action="store_true",
        help="Bei Abweichung nur warnen und immer erfolgreich enden",
    )
    subparsers.add_parser(
        "trust", help="Die geprüfte CA ausdrücklich in alle Vertrauensspeicher installieren"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run export, status or explicit trust installation from the repository root."""
    args = _build_parser().parse_args(argv)
    manager = LocalCATrustManager(
        repo_root=Path(__file__).resolve().parents[2],
        home=Path.home(),
    )
    try:
        if args.command == "export":
            fingerprint = manager.export_current_ca()
            print(f"Caddy-Root-CA exportiert: {fingerprint}")
            return 0
        if args.command == "status":
            report = manager.status()
            if args.warn_only:
                if not report.is_trusted:
                    print(
                        "Hinweis: Die aktuelle Caddy-CA ist noch nicht in allen Browsern "
                        "vertrauenswürdig. Führe `make trust-local-ca` aus."
                    )
                return 0
            _print_status(report, out=sys.stdout)
            return 0 if report.is_trusted else 1

        print(
            "Bitte Firefox und Codex vollständig schließen, "
            "bevor NSS-Datenbanken geändert werden.",
            flush=True,
        )
        print(
            "Die systemweite Installation verwendet anschließend sichtbar `sudo`.",
            flush=True,
        )
        report = manager.trust()
        if report.changed:
            print("Aktualisiert: " + ", ".join(report.changed))
        else:
            print("Alle Vertrauensspeicher enthielten bereits die aktuelle Caddy-CA.")
        print("Firefox und Codex müssen vor der Browserprüfung vollständig neu gestartet werden.")
        return 0
    except TrustError as exc:
        if args.command == "status" and getattr(args, "warn_only", False):
            print(f"Hinweis: {exc} Führe danach `make trust-local-ca` aus.")
            return 0
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
