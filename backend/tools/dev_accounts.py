"""Provision local browser personas and a reusable modular learning landscape.

Why:
    Developers and browser agents need stable teacher/student identities without
    weakening the isolated users created by automated feature tests. This tool
    provisions those identities through Keycloak and creates all learning data
    through the same authenticated APIs used by production browsers.

Security:
    The command refuses every non-local Web, Keycloak, Storage, or H5P URL.
    AI may use loopback or a remote HTTPS provider with the public CA bundle.
    Credentials stay in the ignored local ``.env`` file and are never logged;
    destructive reset operations remain owner-bound to the dedicated teacher.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import secrets
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_STATE_PATH = PROJECT_ROOT / ".tmp" / "dev-accounts-state.json"
H5P_FIXTURE_ROOT = PROJECT_ROOT / "backend" / "tests_e2e" / "fixtures" / "h5p" / "minimal"

COURSE_TITLE = "GUSTAV Browser-Test"
UNIT_TITLE = "Digitale Systeme untersuchen"
LOCAL_HOSTS = frozenset({"app.localhost", "id.localhost", "localhost", "127.0.0.1", "::1"})
DEV_CREDENTIAL_KEYS = (
    "DEV_TEACHER_EMAIL",
    "DEV_TEACHER_PASSWORD",
    "DEV_STUDENT_EMAIL",
    "DEV_STUDENT_PASSWORD",
)


FIXTURE_SPEC: dict[str, Any] = {
    "course_title": COURSE_TITLE,
    "unit_title": UNIT_TITLE,
    "unit_type": "modular",
    "phases": [
        {
            "title": "Orientierung",
            "modules": [
                {
                    "key": "start",
                    "title": "Start und Überblick",
                    "required_prereq_count": 0,
                    "materials": [
                        {
                            "kind": "markdown",
                            "title": "Worum geht es?",
                            "body_md": (
                                "## Digitale Systeme\n\n"
                                "In dieser Testlandschaft untersuchst du Informationen, "
                                "Programme und Netze. Die Inhalte sind synthetisch und "
                                "enthalten keine personenbezogenen Daten."
                            ),
                        },
                        {
                            "kind": "image",
                            "title": "Bausteine eines digitalen Systems",
                            "alt_text": (
                                "Drei farbige Felder stehen für Eingabe, Verarbeitung und Ausgabe."
                            ),
                        },
                    ],
                    "tasks": [
                        {
                            "key": "start_submission",
                            "kind": "native",
                            "instruction_md": (
                                "Erkläre in zwei Sätzen, was ein digitales System auszeichnet."
                            ),
                            "criteria": [
                                "Die Antwort nennt Eingabe, Verarbeitung oder Ausgabe.",
                                "Die Erklärung ist verständlich formuliert.",
                            ],
                            "teacher_context_md": "Eine kurze, ermutigende Rückmeldung genügt.",
                        }
                    ],
                }
            ],
        },
        {
            "title": "Erarbeitung",
            "modules": [
                {
                    "key": "analysis",
                    "title": "Materialien analysieren",
                    "required_prereq_count": 1,
                    "materials": [
                        {
                            "kind": "markdown",
                            "title": "Quellen kritisch lesen",
                            "body_md": (
                                "## Prüffragen\n\n"
                                "Wer stellt eine Behauptung auf? Welche Belege werden genannt? "
                                "Welche Informationen fehlen für eine sichere Einordnung?"
                            ),
                        },
                        {
                            "kind": "markdown",
                            "title": "Zwei Perspektiven",
                            "body_md": (
                                "## Vergleich\n\nPerspektive A betont Chancen, "
                                "Perspektive B mögliche Risiken."
                            ),
                        },
                        {
                            "kind": "image",
                            "title": "Vereinfachtes Datendiagramm",
                            "alt_text": "Ein Balkendiagramm mit den Werten vier, sieben und fünf.",
                        },
                        {"kind": "pdf", "title": "Quellenblatt als PDF"},
                    ],
                    "tasks": [
                        {
                            "key": "analysis_native",
                            "kind": "native",
                            "instruction_md": (
                                "Vergleiche die beiden Perspektiven und begründe deine Einordnung."
                            ),
                            "criteria": [
                                "Beide Perspektiven werden berücksichtigt.",
                                "Die Einordnung wird begründet.",
                            ],
                        },
                        {
                            "key": "analysis_visual",
                            "kind": "visual",
                            "instruction_md": (
                                "Lade ein Bild oder PDF mit deiner markierten Diagrammanalyse hoch."
                            ),
                            "criteria": ["Auffällige Werte sind nachvollziehbar markiert."],
                        },
                    ],
                },
                {
                    "key": "programming",
                    "title": "Programme entwickeln",
                    "required_prereq_count": 1,
                    "materials": [
                        {
                            "kind": "markdown",
                            "title": "Vom Algorithmus zum Programm",
                            "body_md": (
                                "## Vorgehen\n\nPlane, implementiere, teste und "
                                "verbessere dein digitales Produkt."
                            ),
                        },
                        {
                            "kind": "markdown",
                            "title": "Dateiformate im Überblick",
                            "body_md": (
                                "Scratch nutzt `.sb3`, Calliope MakeCode `.hex` und Filius `.fls`."
                            ),
                        },
                    ],
                    "tasks": [
                        {
                            "key": "scratch",
                            "kind": "scratch",
                            "instruction_md": (
                                "Erstelle eine kleine Scratch-Animation und lade die "
                                "`.sb3`-Datei hoch."
                            ),
                            "criteria": [
                                "Das Projekt enthält mindestens eine nachvollziehbare Interaktion."
                            ],
                        },
                        {
                            "key": "calliope",
                            "kind": "calliope",
                            "instruction_md": (
                                "Programmiere eine Anzeige für den Calliope mini und "
                                "lade die `.hex`-Datei hoch."
                            ),
                            "criteria": ["Das Programm erzeugt eine sichtbare Ausgabe."],
                        },
                        {
                            "key": "filius",
                            "kind": "filius",
                            "instruction_md": (
                                "Baue ein kleines Filius-Netz und lade die `.fls`-Datei hoch."
                            ),
                            "criteria": ["Mindestens zwei Geräte sind sinnvoll verbunden."],
                        },
                    ],
                },
                {
                    "key": "interactive",
                    "title": "Interaktiv üben und reflektieren",
                    "required_prereq_count": 1,
                    "materials": [
                        {
                            "kind": "markdown",
                            "title": "Interaktives Arbeiten",
                            "body_md": (
                                "## Ablauf\n\nBearbeite das H5P-Beispiel und "
                                "reflektiere anschließend im KI-Dialog."
                            ),
                        },
                        {
                            "kind": "markdown",
                            "title": "Gesprächsregeln",
                            "body_md": (
                                "Begründe Beobachtungen und frage nach Belegen, "
                                "wenn etwas unklar bleibt."
                            ),
                        },
                    ],
                    "tasks": [
                        {
                            "key": "h5p",
                            "kind": "h5p",
                            "instruction_md": "Bearbeite das interaktive H5P-Beispiel.",
                            "criteria": [],
                        },
                        {
                            "key": "dialog",
                            "kind": "dialog",
                            "instruction_md": (
                                "Reflektiere deine Beobachtungen im Gespräch mit Ada."
                            ),
                            "criteria": ["Beobachtungen werden mit einem Beispiel begründet."],
                            "teacher_context_md": (
                                "Der Dialog dient als reproduzierbare lokale Browser-Fixture."
                            ),
                            "dialog": {
                                "partner_name": "Ada",
                                "partner_description_md": (
                                    "Ada hilft dir, Aussagen über digitale Systeme zu prüfen."
                                ),
                                "role_md": (
                                    "Frage sachlich nach Belegen und bleibe bei digitalen Systemen."
                                ),
                                "learning_goal_md": (
                                    "Der Schüler begründet eine Beobachtung mit einem "
                                    "konkreten Beispiel."
                                ),
                                "opening_message_md": (
                                    "Welche Beobachtung über digitale Systeme möchtest "
                                    "du untersuchen?"
                                ),
                                "response_mode": "free_text",
                                "max_rounds": 4,
                                "closing_prompt_md": "Fasse deine wichtigste Erkenntnis zusammen.",
                            },
                        },
                    ],
                },
                {
                    "key": "practice_native",
                    "title": "Grundlagen wiederholen",
                    "module_kind": "practice",
                    "required_prereq_count": 1,
                    "materials": [],
                    "tasks": [
                        {
                            "key": "practice_native_task",
                            "kind": "native",
                            "instruction_md": (
                                "Erkläre das EVA-Prinzip an einem selbst gewählten digitalen System."
                            ),
                            "criteria": [
                                "Eingabe, Verarbeitung und Ausgabe werden korrekt zugeordnet.",
                                "Das gewählte Beispiel ist nachvollziehbar erklärt.",
                            ],
                            "teacher_context_md": (
                                "Bewerte fachlich knapp und ermutige zu einem konkreten Beispiel."
                            ),
                            "model_solution_md": (
                                "Bei einem Fahrkartenautomaten ist die Auswahl des Ziels die Eingabe. "
                                "Das System berechnet den Preis und zeigt ihn als Ausgabe an."
                            ),
                        }
                    ],
                },
                {
                    "key": "practice_h5p",
                    "title": "Interaktiv wiederholen",
                    "module_kind": "practice",
                    "required_prereq_count": 1,
                    "materials": [],
                    "tasks": [
                        {
                            "key": "practice_h5p_task",
                            "kind": "h5p",
                            "instruction_md": "Bearbeite die interaktive Wiederholungsaufgabe.",
                            "criteria": [],
                        }
                    ],
                },
            ],
        },
        {
            "title": "Transfer",
            "modules": [
                {
                    "key": "transfer",
                    "title": "Transferaufgabe",
                    "required_prereq_count": 2,
                    "materials": [
                        {
                            "kind": "markdown",
                            "title": "Neues Szenario",
                            "body_md": (
                                "## Schulnetz\n\nEine Projektgruppe plant ein "
                                "sicheres und verständliches Schulnetz."
                            ),
                        },
                        {
                            "kind": "markdown",
                            "title": "Entscheidungshilfe",
                            "body_md": (
                                "Berücksichtige technische Funktion, Datenschutz "
                                "und Verständlichkeit."
                            ),
                        },
                    ],
                    "tasks": [
                        {
                            "key": "transfer_native",
                            "kind": "native",
                            "instruction_md": (
                                "Entwirf eine begründete Lösung für das neue Szenario."
                            ),
                            "criteria": [
                                "Die Lösung ist technisch plausibel.",
                                "Datenschutz wird berücksichtigt.",
                            ],
                            "teacher_context_md": (
                                "Achte besonders auf die Verbindung der zuvor "
                                "erarbeiteten Perspektiven."
                            ),
                            "max_attempts": 3,
                        }
                    ],
                },
                {
                    "key": "finish",
                    "title": "Abschluss",
                    "required_prereq_count": 1,
                    "materials": [
                        {
                            "kind": "markdown",
                            "title": "Rückblick",
                            "body_md": (
                                "## Rückblick\n\nVerbinde fachliche Erkenntnisse "
                                "mit deinem eigenen Arbeitsprozess."
                            ),
                        }
                    ],
                    "tasks": [
                        {
                            "key": "finish_native",
                            "kind": "native",
                            "instruction_md": (
                                "Was hast du gelernt und welche Frage ist offen geblieben?"
                            ),
                            "criteria": [
                                "Die Reflexion nennt eine Erkenntnis und eine offene Frage."
                            ],
                        }
                    ],
                },
            ],
        },
    ],
}

FIXTURE_EDGES: tuple[tuple[str, str], ...] = (
    ("start", "analysis"),
    ("start", "programming"),
    ("start", "interactive"),
    ("analysis", "transfer"),
    ("programming", "transfer"),
    ("interactive", "transfer"),
    ("transfer", "finish"),
    ("start", "practice_native"),
    ("start", "practice_h5p"),
)

PRACTICE_MODULE_KEYS = frozenset({"practice_native", "practice_h5p"})


def require_local_url(value: str) -> None:
    """Reject URLs that could make the local tool mutate a remote deployment."""

    parsed = urlsplit((value or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in LOCAL_HOSTS:
        raise RuntimeError(f"local URL required, got host={host!r}")


def require_ai_url(value: str) -> None:
    """Allow loopback inference or a configured remote provider over HTTPS."""

    parsed = urlsplit((value or "").strip())
    host = (parsed.hostname or "").lower()
    is_loopback = host in LOCAL_HOSTS
    secure_scheme = parsed.scheme in ({"http", "https"} if is_loopback else {"https"})
    if not host or not secure_scheme or parsed.username is not None or parsed.password is not None:
        raise RuntimeError(f"secure AI URL required, got host={host!r}")


def ai_verify_for_url(value: str, *, local_verify: str | bool) -> str | bool:
    """Select the local Caddy CA or the public CA bundle for the AI provider."""

    host = (urlsplit((value or "").strip()).hostname or "").lower()
    return local_verify if host in LOCAL_HOSTS else requests.certs.where()


def _unquote_env(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _unquote_env(value)
    return values


def _credential_domain(values: dict[str, str]) -> str:
    explicit = values.get("E2E_EMAIL_DOMAIN", "").strip().lstrip("@")
    if explicit:
        return explicit
    allowed = values.get("ALLOWED_REGISTRATION_DOMAINS", "")
    for item in allowed.split(","):
        domain = item.strip().lstrip("@")
        if domain:
            return domain
    return "example.com"


def _generate_password() -> str:
    # The prefix makes every generated value satisfy the configured Keycloak policy.
    return "Aa1!" + secrets.token_urlsafe(24)


def _write_env_values(path: Path, replacements: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in replacements:
                if key not in seen:
                    output.append(f"{key}={replacements[key]}")
                    seen.add(key)
                # Duplicate secret keys make shell and dotenv parsing ambiguous.
                continue
        output.append(line)
    missing = [key for key in DEV_CREDENTIAL_KEYS if key not in seen]
    if missing:
        if output and output[-1] != "":
            output.append("")
        output.append("# Local browser personas (generated; never commit .env)")
        output.extend(f"{key}={replacements[key]}" for key in missing)

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write("\n".join(output) + "\n")
        os.fchmod(handle.fileno(), 0o600)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    path.chmod(0o600)


def ensure_env_credentials(path: Path = DEFAULT_ENV_PATH) -> dict[str, str]:
    """Fill only missing persona settings and preserve all operator-owned values."""

    if not path.is_file():
        raise RuntimeError(f"local .env file missing: {path}")
    values = _read_env_values(path)
    domain = _credential_domain(values)
    replacements = {
        "DEV_TEACHER_EMAIL": values.get("DEV_TEACHER_EMAIL", "").strip() or f"dev.teacher@{domain}",
        "DEV_TEACHER_PASSWORD": (
            values.get("DEV_TEACHER_PASSWORD", "").strip() or _generate_password()
        ),
        "DEV_STUDENT_EMAIL": values.get("DEV_STUDENT_EMAIL", "").strip() or f"dev.student@{domain}",
        "DEV_STUDENT_PASSWORD": (
            values.get("DEV_STUDENT_PASSWORD", "").strip() or _generate_password()
        ),
    }
    _write_env_values(path, replacements)
    return replacements


def write_state(path: Path, state: dict[str, Any]) -> None:
    """Persist a private, atomic recovery marker for tool-owned global resources."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        os.fchmod(handle.fileno(), 0o600)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    path.chmod(0o600)


def read_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def h5p_content_id_for_cleanup(state: dict[str, Any] | None) -> str | None:
    raw = str((state or {}).get("h5p_content_id") or "")
    return raw if raw.isascii() and raw.isdigit() else None


def _is_complete_fixture_state(state: dict[str, Any] | None) -> bool:
    """Reject truncated recovery manifests instead of treating them as ready."""

    if not isinstance(state, dict) or state.get("status") != "complete":
        return False
    scalar_keys = ("course_id", "unit_id", "h5p_content_id", "dialog_session_id")
    if any(not str(state.get(key) or "").strip() for key in scalar_keys):
        return False
    module_keys = {str(module["key"]) for _, module in _iter_modules()}
    task_keys = {str(task["key"]) for _, module in _iter_modules() for task in module["tasks"]}
    module_ids = state.get("module_ids")
    section_ids = state.get("section_ids")
    task_ids = state.get("task_ids")
    return (
        isinstance(module_ids, dict)
        and set(module_ids) == module_keys
        and all(str(value or "").strip() for value in module_ids.values())
        and isinstance(section_ids, dict)
        and set(section_ids) == module_keys
        and all(str(value or "").strip() for value in section_ids.values())
        and isinstance(task_ids, dict)
        and set(task_ids) == task_keys
        and all(str(value or "").strip() for value in task_ids.values())
    )


def _is_additive_practice_upgrade_state(state: dict[str, Any] | None) -> bool:
    """Recognize the previous complete fixture without accepting arbitrary state."""

    if not isinstance(state, dict) or state.get("status") not in {"complete", "upgrading"}:
        return False
    scalar_keys = ("course_id", "unit_id", "h5p_content_id", "dialog_session_id")
    if any(not str(state.get(key) or "").strip() for key in scalar_keys):
        return False
    expected_modules = {str(module["key"]) for _, module in _iter_modules()}
    expected_tasks = {
        str(task["key"]) for _, module in _iter_modules() for task in module["tasks"]
    }
    legacy_modules = expected_modules - PRACTICE_MODULE_KEYS
    legacy_tasks = expected_tasks - {"practice_native_task", "practice_h5p_task"}
    module_ids = state.get("module_ids")
    section_ids = state.get("section_ids")
    task_ids = state.get("task_ids")
    return (
        isinstance(module_ids, dict)
        and legacy_modules <= set(module_ids) <= expected_modules
        and isinstance(section_ids, dict)
        and legacy_modules <= set(section_ids) <= expected_modules
        and isinstance(task_ids, dict)
        and legacy_tasks <= set(task_ids) <= expected_tasks
    )


def fixture_decision(state: dict[str, Any] | None, *, course_count: int) -> str:
    """Choose an idempotent action without guessing about untracked existing data."""

    status = str((state or {}).get("status") or "")
    if status == "complete" and course_count == 1:
        if _is_complete_fixture_state(state):
            return "ready"
        if _is_additive_practice_upgrade_state(state):
            return "upgrade"
        return "rebuild"
    if status == "upgrading" and course_count == 1:
        return "upgrade" if _is_additive_practice_upgrade_state(state) else "rebuild"
    if status == "complete" and not _is_complete_fixture_state(state):
        return "rebuild"
    # A "building" marker proves that the tool owns an interrupted fixture. It
    # is therefore safe to remove that partial state and start again.
    if status == "building":
        return "rebuild"
    if status == "complete" and course_count == 0:
        return "rebuild"
    if state is None and course_count == 0:
        return "create"
    return "explicit_reset"


def _load_dotenv(path: Path) -> None:
    # Import lazily so unit tests do not accidentally load operator secrets.
    from dotenv import load_dotenv

    load_dotenv(path, override=False)


def _verify_option() -> str | bool:
    configured = os.getenv("REQUESTS_CA_BUNDLE", "").strip()
    if configured:
        return configured
    local_bundle = PROJECT_ROOT / ".tmp" / "caddy-root.crt"
    return str(local_bundle) if local_bundle.is_file() and local_bundle.stat().st_size else True


@dataclass(frozen=True)
class DevConfig:
    env_path: Path
    state_path: Path
    web_base: str
    kc_base: str
    realm: str
    admin_realm: str
    admin_client_id: str
    admin_client_secret: str
    admin_user: str
    admin_password: str
    storage_base: str
    openai_base: str
    openai_api_key: str
    ai_text_model: str
    verify: str | bool
    timeout_seconds: float
    ai_timeout_seconds: float

    @classmethod
    def from_environment(cls, *, env_path: Path, state_path: Path) -> "DevConfig":
        return cls(
            env_path=env_path,
            state_path=state_path,
            web_base=(os.getenv("WEB_BASE") or "https://app.localhost").rstrip("/"),
            kc_base=(
                os.getenv("KC_BASE") or os.getenv("KC_PUBLIC_BASE_URL") or "https://id.localhost"
            ).rstrip("/"),
            realm=os.getenv("KC_REALM", "gustav"),
            admin_realm=os.getenv("KC_ADMIN_REALM", "master"),
            admin_client_id=os.getenv("KC_ADMIN_CLIENT_ID", "gustav-admin-cli"),
            admin_client_secret=os.getenv("KC_ADMIN_CLIENT_SECRET", "").strip(),
            admin_user=(
                os.getenv("KEYCLOAK_ADMIN") or os.getenv("KC_ADMIN_USERNAME") or "admin"
            ).strip(),
            admin_password=(
                os.getenv("KEYCLOAK_ADMIN_PASSWORD") or os.getenv("KC_ADMIN_PASSWORD") or "admin"
            ).strip(),
            storage_base=(os.getenv("SUPABASE_URL") or "http://127.0.0.1:54321").rstrip("/"),
            openai_base=(os.getenv("OPENAI_BASE_URL") or "").rstrip("/"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            ai_text_model=os.getenv("AI_TEXT_MODEL", "").strip(),
            verify=_verify_option(),
            timeout_seconds=float(os.getenv("DEV_ACCOUNTS_TIMEOUT_SECONDS", "30")),
            ai_timeout_seconds=float(os.getenv("DEV_ACCOUNTS_AI_TIMEOUT_SECONDS", "180")),
        )

    def assert_safe_endpoints(self) -> None:
        for value in (self.web_base, self.kc_base, self.storage_base):
            require_local_url(value)
        require_ai_url(self.openai_base)


def _safe_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        error = payload.get("detail") or payload.get("error") or payload.get("status")
        return f"HTTP {response.status_code}: {error}" if error else f"HTTP {response.status_code}"
    return f"HTTP {response.status_code}"


def _expect(
    response: requests.Response, expected: Iterable[int], *, action: str
) -> requests.Response:
    if response.status_code not in set(expected):
        raise RuntimeError(f"{action} failed: {_safe_error(response)}")
    return response


def run_preflight(config: DevConfig) -> None:
    """Check local dependencies and the configured AI provider before mutation."""

    if not config.openai_base or not config.ai_text_model:
        raise RuntimeError("AI preflight failed: OPENAI_BASE_URL and AI_TEXT_MODEL are required")
    config.assert_safe_endpoints()
    session = requests.Session()
    session.verify = config.verify
    timeout = config.timeout_seconds
    _expect(
        session.get(f"{config.web_base}/health", timeout=timeout),
        {200},
        action="Web preflight",
    )
    _expect(
        session.get(
            f"{config.kc_base}/realms/{config.realm}/.well-known/openid-configuration",
            timeout=timeout,
        ),
        {200},
        action="Keycloak preflight",
    )
    h5p = _expect(
        session.get(f"{config.web_base}/h5p/healthz", timeout=timeout),
        {200},
        action="H5P preflight",
    )
    h5p_body = h5p.json() if h5p.content else {}
    if not isinstance(h5p_body, dict) or not bool((h5p_body.get("storage") or {}).get("ok")):
        raise RuntimeError("H5P preflight failed: storage not ready")
    _expect(
        session.get(f"{config.storage_base}/storage/v1/status", timeout=timeout),
        {200},
        action="Storage preflight",
    )
    headers = {"Authorization": f"Bearer {config.openai_api_key}"} if config.openai_api_key else {}
    models = _expect(
        session.get(
            f"{config.openai_base}/models",
            headers=headers,
            timeout=timeout,
            verify=ai_verify_for_url(config.openai_base, local_verify=config.verify),
        ),
        {200},
        action="AI preflight",
    ).json()
    data = models.get("data") if isinstance(models, dict) else models
    ids = {str(item.get("id")) if isinstance(item, dict) else str(item) for item in (data or [])}
    if config.ai_text_model not in ids:
        raise RuntimeError(
            f"AI preflight failed: configured model {config.ai_text_model!r} is unavailable"
        )


class KeycloakAdmin:
    """Small Keycloak Admin API adapter dedicated to the local personas."""

    def __init__(self, config: DevConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify

    def token(self) -> str:
        if self.config.admin_client_secret:
            response = self.session.post(
                f"{self.config.kc_base}/realms/{self.config.admin_realm}/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.admin_client_id,
                    "client_secret": self.config.admin_client_secret,
                },
                timeout=self.config.timeout_seconds,
            )
            if response.ok and (response.json() or {}).get("access_token"):
                return str(response.json()["access_token"])
        response = _expect(
            self.session.post(
                f"{self.config.kc_base}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": self.config.admin_user,
                    "password": self.config.admin_password,
                },
                timeout=self.config.timeout_seconds,
            ),
            {200},
            action="Keycloak admin authentication",
        )
        token = (response.json() or {}).get("access_token")
        if not token:
            raise RuntimeError("Keycloak admin authentication failed: access token missing")
        return str(token)

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def ensure_user(
        self,
        *,
        token: str,
        email: str,
        password: str,
        role: str,
        display_name: str,
    ) -> str:
        """Create or synchronize one local persona while preserving its Keycloak ID."""

        base = f"{self.config.kc_base}/admin/realms/{self.config.realm}"
        lookup = _expect(
            self.session.get(
                f"{base}/users",
                headers=self._headers(token),
                params={"email": email, "exact": "true"},
                timeout=self.config.timeout_seconds,
            ),
            {200},
            action="Keycloak user lookup",
        ).json()
        user_id = str(lookup[0].get("id")) if isinstance(lookup, list) and lookup else ""
        payload = {
            "username": email,
            "email": email,
            "firstName": "Dev",
            "lastName": "Lehrkraft" if role == "teacher" else "Schüler",
            "attributes": {"display_name": [display_name]},
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
        }
        if not user_id:
            _expect(
                self.session.post(
                    f"{base}/users",
                    headers=self._headers(token),
                    json=payload,
                    timeout=self.config.timeout_seconds,
                ),
                {201, 204},
                action="Keycloak user creation",
            )
            lookup = _expect(
                self.session.get(
                    f"{base}/users",
                    headers=self._headers(token),
                    params={"email": email, "exact": "true"},
                    timeout=self.config.timeout_seconds,
                ),
                {200},
                action="Keycloak created-user lookup",
            ).json()
            user_id = str(lookup[0].get("id")) if isinstance(lookup, list) and lookup else ""
        else:
            _expect(
                self.session.put(
                    f"{base}/users/{user_id}",
                    headers=self._headers(token),
                    json=payload,
                    timeout=self.config.timeout_seconds,
                ),
                {200, 204},
                action="Keycloak user update",
            )
        if not user_id:
            raise RuntimeError("Keycloak user provisioning failed: user id missing")
        _expect(
            self.session.put(
                f"{base}/users/{user_id}/reset-password",
                headers=self._headers(token),
                json={"type": "password", "value": password, "temporary": False},
                timeout=self.config.timeout_seconds,
            ),
            {200, 204},
            action="Keycloak password synchronization",
        )
        role_payload = _expect(
            self.session.get(
                f"{base}/roles/{role}",
                headers=self._headers(token),
                timeout=self.config.timeout_seconds,
            ),
            {200},
            action="Keycloak role lookup",
        ).json()
        _expect(
            self.session.post(
                f"{base}/users/{user_id}/role-mappings/realm",
                headers=self._headers(token),
                json=[role_payload],
                timeout=self.config.timeout_seconds,
            ),
            {200, 204},
            action="Keycloak role assignment",
        )
        return user_id


def _parse_login_form(markup: str, base_url: str) -> tuple[str, dict[str, str]]:
    match = re.search(
        r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"[^>]*>(.*?)</form>',
        markup,
        re.I | re.S,
    )
    if not match:
        raise RuntimeError("OIDC login failed: Keycloak login form missing")
    fields = dict(
        re.findall(
            r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"',
            match.group(2),
            re.I,
        )
    )
    action = urljoin(base_url, html.unescape(match.group(1)))
    return action, {key: html.unescape(value) for key, value in fields.items()}


class BrowserSession:
    """HTTP browser session that completes the real OIDC authorization-code flow."""

    def __init__(self, config: DevConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify

    def login(self, *, email: str, password: str) -> None:
        login_page = _expect(
            self.session.get(
                f"{self.config.web_base}/auth/login",
                allow_redirects=True,
                timeout=self.config.timeout_seconds,
            ),
            {200},
            action="OIDC login page",
        )
        action, fields = _parse_login_form(login_page.text, login_page.url)
        fields.update({"username": email, "password": password})
        response = self.session.post(
            action,
            data=fields,
            allow_redirects=True,
            timeout=self.config.timeout_seconds,
        )
        _expect(response, {200, 204}, action="OIDC callback")
        me = _expect(
            self.session.get(f"{self.config.web_base}/api/me", timeout=self.config.timeout_seconds),
            {200},
            action="authenticated session check",
        )
        if not isinstance(me.json(), dict) or not me.json().get("sub"):
            raise RuntimeError("authenticated session check failed: subject missing")

    def request(
        self,
        method: str,
        path: str,
        *,
        expected: Iterable[int] = (200,),
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> requests.Response:
        request_headers = {
            "Origin": self.config.web_base,
            "Referer": f"{self.config.web_base}/",
            **(headers or {}),
        }
        response = self.session.request(
            method,
            urljoin(f"{self.config.web_base}/", path.lstrip("/")),
            json=json_body,
            files=files,
            headers=request_headers,
            params=params,
            timeout=timeout or self.config.timeout_seconds,
        )
        return _expect(response, expected, action=f"{method.upper()} {path}")

    def subject(self) -> str:
        return str(self.request("GET", "/api/me").json()["sub"])


def _build_h5p_fixture() -> bytes:
    if not H5P_FIXTURE_ROOT.is_dir():
        raise RuntimeError(f"H5P fixture missing: {H5P_FIXTURE_ROOT}")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(H5P_FIXTURE_ROOT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(H5P_FIXTURE_ROOT).as_posix())
    return buffer.getvalue()


def _png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR42mNkYPj/n4GBgYGJAQoAHgQCAQ1BDQAAAABJRU5ErkJggg=="
    )


def _pdf_bytes() -> bytes:
    stream = b"BT /F1 16 Tf 72 720 Td (GUSTAV Quellenblatt) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode("ascii"))
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(payload)


def _api_json(
    session: BrowserSession,
    method: str,
    path: str,
    *,
    expected: Iterable[int],
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = session.request(
        method,
        path,
        expected=expected,
        json_body=body,
        headers=headers,
    ).json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {path} failed: JSON object expected")
    return payload


def _create_file_material(
    session: BrowserSession,
    *,
    unit_id: str,
    section_id: str,
    filename: str,
    mime_type: str,
    title: str,
    content: bytes,
    alt_text: str | None = None,
) -> str:
    base_path = f"/api/teaching/units/{unit_id}/sections/{section_id}/materials"
    intent = _api_json(
        session,
        "POST",
        f"{base_path}/upload-intents",
        expected=(200,),
        body={"filename": filename, "mime_type": mime_type, "size_bytes": len(content)},
    )
    upload_headers = {str(key): str(value) for key, value in (intent.get("headers") or {}).items()}
    upload = session.session.put(
        str(intent["url"]),
        data=content,
        headers=upload_headers,
        timeout=session.config.timeout_seconds,
    )
    _expect(upload, {200}, action=f"material upload {filename}")
    material = _api_json(
        session,
        "POST",
        f"{base_path}/finalize",
        expected=(201,),
        body={
            "intent_id": intent["intent_id"],
            "title": title,
            "sha256": hashlib.sha256(content).hexdigest(),
            **({"alt_text": alt_text} if alt_text else {}),
        },
    )
    return str(material["id"])


def _create_materials(
    session: BrowserSession,
    *,
    unit_id: str,
    section_id: str,
    module: dict[str, Any],
) -> None:
    for index, material in enumerate(module["materials"], start=1):
        kind = material["kind"]
        if kind == "markdown":
            _api_json(
                session,
                "POST",
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
                expected=(201,),
                body={"title": material["title"], "body_md": material["body_md"]},
            )
        elif kind == "image":
            _create_file_material(
                session,
                unit_id=unit_id,
                section_id=section_id,
                filename=f"dev-diagram-{index}.png",
                mime_type="image/png",
                title=material["title"],
                alt_text=material["alt_text"],
                content=_png_bytes(),
            )
        elif kind == "pdf":
            _create_file_material(
                session,
                unit_id=unit_id,
                section_id=section_id,
                filename="dev-quellenblatt.pdf",
                mime_type="application/pdf",
                title=material["title"],
                content=_pdf_bytes(),
            )
        else:
            raise RuntimeError(f"unsupported fixture material kind: {kind}")


def _task_payload(task: dict[str, Any], *, h5p_content_id: str) -> dict[str, Any]:
    payload = {
        "instruction_md": task["instruction_md"],
        "criteria": task.get("criteria", []),
    }
    for optional in ("teacher_context_md", "model_solution_md", "max_attempts"):
        if optional in task:
            payload[optional] = task[optional]
    kind = task["kind"]
    if kind == "h5p":
        payload["h5p"] = {"content_id": h5p_content_id, "display_options": {}}
    elif kind == "dialog":
        payload["dialog"] = task["dialog"]
    elif kind != "native":
        payload[kind] = {}
    return payload


def _iter_modules() -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for phase in FIXTURE_SPEC["phases"]:
        for module in phase["modules"]:
            yield phase, module


def _list_all(session: BrowserSession, path: str, *, page_size: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = session.request("GET", path, params={"limit": page_size, "offset": offset})
        page = response.json()
        if not isinstance(page, list):
            raise RuntimeError(f"GET {path} failed: JSON list expected")
        items.extend(item for item in page if isinstance(item, dict))
        if len(page) < page_size:
            return items
        offset += page_size


def _owned_fixture_courses(session: BrowserSession) -> list[dict[str, Any]]:
    return [
        course
        for course in _list_all(session, "/api/teaching/courses", page_size=50)
        if course.get("title") == COURSE_TITLE
    ]


def _list_course_catalog(
    session: BrowserSession,
    *,
    status: str,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """Read the owner-scoped active or archived course catalog."""

    items: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = session.request(
            "GET",
            "/api/teaching/courses",
            params={"status": status, "limit": page_size, "offset": offset},
        )
        payload = response.json()
        page = payload if isinstance(payload, list) else None
        if not isinstance(page, list):
            raise RuntimeError("Course catalog failed: JSON course list expected")
        items.extend(item for item in page if isinstance(item, dict))
        if len(page) < page_size:
            return items
        offset += page_size


def run_product_storage_preflight(session: BrowserSession) -> None:
    """Warm and verify the product's storage adapter without persisting data.

    The existing upload-intent route wires Supabase lazily before it validates
    MIME admission. An intentionally unsupported MIME type must therefore
    produce ``mime_not_allowed`` without creating an upload-intent row.
    """

    for unit in _list_all(session, "/api/teaching/units", page_size=50):
        unit_id = str(unit.get("id") or "")
        if not unit_id:
            continue
        sections = _list_all(
            session,
            f"/api/teaching/units/{unit_id}/sections",
            page_size=50,
        )
        section_id = str((sections[0] if sections else {}).get("id") or "")
        if not section_id:
            continue
        response = session.request(
            "POST",
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
            expected=(400,),
            json_body={
                "filename": "dev-accounts-storage-preflight.invalid",
                "mime_type": "application/x-gustav-storage-preflight",
                "size_bytes": 1,
            },
        )
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("detail") != "mime_not_allowed":
            raise RuntimeError("Product storage preflight failed: unexpected response")
        return


def run_product_worker_preflight(session: BrowserSession) -> None:
    """Require a healthy worker with the lifecycle command boundary installed."""

    payload = session.request("GET", "/internal/health/learning-worker").json()
    checks = payload.get("checks") if isinstance(payload, dict) else None
    lifecycle = next(
        (
            check
            for check in checks or []
            if isinstance(check, dict) and check.get("check") == "lifecycle_commands"
        ),
        None,
    )
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "healthy"
        or not isinstance(lifecycle, dict)
        or lifecycle.get("status") != "ok"
    ):
        raise RuntimeError("Learning worker preflight failed: lifecycle_commands unavailable")


def _wait_for_deletion_jobs(
    session: BrowserSession,
    job_ids: set[str],
    *,
    timeout_seconds: float,
) -> None:
    """Wait for explicit completed states and fail closed on job errors."""

    deadline = time.monotonic() + timeout_seconds
    pending = set(job_ids)
    while pending and time.monotonic() < deadline:
        for job_id in list(pending):
            payload = session.request(
                "GET",
                f"/api/teaching/course-deletion-jobs/{job_id}",
            ).json()
            status = str(payload.get("status") or "") if isinstance(payload, dict) else ""
            if status == "completed":
                pending.remove(job_id)
            elif status == "failed":
                error_code = payload.get("error_code") or "unknown"
                raise RuntimeError(f"course deletion failed: {error_code}")
            elif status not in {"pending", "processing"}:
                raise RuntimeError("course deletion poll failed: invalid job state")
        if pending:
            time.sleep(1)
    if pending:
        raise RuntimeError(f"course deletion timed out for {len(pending)} job(s)")


def _delete_owned_data(
    session: BrowserSession,
    *,
    timeout_seconds: float,
    prior_state: dict[str, Any] | None = None,
    state_path: Path | None = None,
) -> None:
    run_product_worker_preflight(session)

    open_jobs = _list_all(
        session,
        "/api/teaching/course-deletion-jobs",
        page_size=100,
    )
    active_courses = _list_course_catalog(session, status="active")
    archived_courses = _list_course_catalog(session, status="archived")
    units = _list_all(session, "/api/teaching/units", page_size=100)

    targets_by_course: dict[str, dict[str, Any]] = {}
    for job in open_jobs:
        course_id = str(job.get("course_id") or "")
        title = str(job.get("course_title") or "")
        job_id = str(job.get("id") or "")
        if course_id and title and job_id:
            targets_by_course[course_id] = {
                "id": course_id,
                "title": title,
                "original_status": "deleting",
                "job_id": job_id,
            }
    for original_status, courses in (
        ("active", active_courses),
        ("archived", archived_courses),
    ):
        for course in courses:
            course_id = str(course.get("id") or "")
            title = str(course.get("title") or "")
            if course_id and title and course_id not in targets_by_course:
                targets_by_course[course_id] = {
                    "id": course_id,
                    "title": title,
                    "original_status": original_status,
                    "job_id": None,
                }

    reset_targets = {
        "courses": list(targets_by_course.values()),
        "unit_ids": [str(unit.get("id")) for unit in units if unit.get("id")],
    }
    recovery_state = dict(prior_state or {})
    if state_path is not None:
        recovery_state.update({"status": "resetting", "reset_targets": reset_targets})
        write_state(state_path, recovery_state)

    resumed_job_ids: set[str] = set()
    for job in open_jobs:
        job_id = str(job.get("id") or "")
        if not job_id:
            continue
        if job.get("status") == "failed":
            course_id = str(job.get("course_id") or "")
            title = str(job.get("course_title") or "")
            response = session.request(
                "POST",
                f"/api/teaching/courses/{course_id}/deletion-jobs",
                expected=(202,),
                json_body={"confirmation_title": title, "confirm_student_data_loss": True},
            ).json()
            job_id = str(response.get("id") or "") if isinstance(response, dict) else ""
            if course_id in targets_by_course:
                targets_by_course[course_id]["job_id"] = job_id or None
                if state_path is not None:
                    recovery_state["reset_targets"] = reset_targets
                    write_state(state_path, recovery_state)
        if job_id:
            resumed_job_ids.add(job_id)
    _wait_for_deletion_jobs(
        session,
        resumed_job_ids,
        timeout_seconds=timeout_seconds,
    )

    for course in archived_courses:
        course_id = str(course.get("id") or "")
        if course_id:
            session.request(
                "POST",
                f"/api/teaching/courses/{course_id}/restore",
                expected=(200,),
            )

    for unit_id in reset_targets["unit_ids"]:
        if unit_id:
            session.request("DELETE", f"/api/teaching/units/{unit_id}", expected=(204,))

    created_job_ids: set[str] = set()
    for target in reset_targets["courses"]:
        if target["job_id"]:
            continue
        response = session.request(
            "POST",
            f"/api/teaching/courses/{target['id']}/deletion-jobs",
            expected=(202,),
            json_body={
                "confirmation_title": target["title"],
                "confirm_student_data_loss": True,
            },
        ).json()
        job_id = str(response.get("id") or "") if isinstance(response, dict) else ""
        if not job_id:
            raise RuntimeError("course deletion failed: job id missing")
        target["job_id"] = job_id
        created_job_ids.add(job_id)
        if state_path is not None:
            recovery_state["reset_targets"] = reset_targets
            write_state(state_path, recovery_state)
    _wait_for_deletion_jobs(
        session,
        created_job_ids,
        timeout_seconds=timeout_seconds,
    )


def _delete_tool_h5p(session: BrowserSession, state: dict[str, Any] | None) -> None:
    content_id = h5p_content_id_for_cleanup(state)
    if not content_id:
        return
    response = session.session.delete(
        f"{session.config.web_base}/h5p/contents/{content_id}",
        headers={
            "Origin": session.config.web_base,
            "Referer": f"{session.config.web_base}/h5p/editor",
        },
        timeout=session.config.timeout_seconds,
    )
    _expect(response, {204, 404}, action="tool-owned H5P cleanup")


def _import_h5p(session: BrowserSession) -> str:
    response = session.request(
        "POST",
        "/h5p/contents/import",
        expected=(200, 201),
        files={"file": ("gustav-dev-minimal.h5p", _build_h5p_fixture(), "application/zip")},
        timeout=60,
    )
    content_id = str((response.json() or {}).get("content_id") or "")
    if not content_id.isascii() or not content_id.isdigit():
        raise RuntimeError("H5P import failed: numeric content id missing")
    return content_id


def _wait_for_feedback(
    student: BrowserSession,
    *,
    course_id: str,
    task_id: str,
    submission_id: str,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        submissions = student.request(
            "GET",
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            params={"limit": 20, "offset": 0},
        ).json()
        current = next((item for item in submissions if str(item.get("id")) == submission_id), None)
        if current and current.get("analysis_status") == "completed" and current.get("feedback_md"):
            return
        if current and current.get("analysis_status") == "failed":
            error_code = current.get("error_code") or "unknown error"
            raise RuntimeError(f"fixture feedback failed: {error_code}")
        time.sleep(2)
    raise RuntimeError("fixture feedback timed out")


def create_landscape(
    config: DevConfig,
    *,
    teacher: BrowserSession,
    student: BrowserSession,
) -> dict[str, Any]:
    """Create the complete fixture through authenticated product APIs.

    The teacher session must own every created authoring resource. The student
    session must belong to the provisioned learner persona. A private recovery
    marker is persisted before global H5P content or product data is created.
    """

    state: dict[str, Any] = {"status": "building", "version": 3}
    write_state(config.state_path, state)

    h5p_content_id = _import_h5p(teacher)
    state["h5p_content_id"] = h5p_content_id
    write_state(config.state_path, state)

    course = _api_json(
        teacher,
        "POST",
        "/api/teaching/courses",
        expected=(201,),
        body={
            "title": COURSE_TITLE,
            "subject": "Informatik",
            "grade_level": "Jahrgangsübergreifend",
            "school_year_start": time.gmtime().tm_year,
        },
    )
    unit = _api_json(
        teacher,
        "POST",
        "/api/teaching/units",
        expected=(201,),
        body={"title": UNIT_TITLE, "unit_type": "modular"},
    )
    course_id = str(course["id"])
    unit_id = str(unit["id"])
    state.update(
        {"course_id": course_id, "course_title": COURSE_TITLE, "unit_id": unit_id}
    )
    write_state(config.state_path, state)

    phases_payload = teacher.request("GET", f"/api/teaching/units/{unit_id}/phases").json()
    if not isinstance(phases_payload, list) or not phases_payload:
        raise RuntimeError("modular unit creation failed: default phase missing")
    phase_ids: dict[str, str] = {}
    first_phase_id = str(phases_payload[0]["id"])
    first_title = str(FIXTURE_SPEC["phases"][0]["title"])
    _api_json(
        teacher,
        "PATCH",
        f"/api/teaching/units/{unit_id}/phases/{first_phase_id}",
        expected=(200,),
        body={"title": first_title},
    )
    phase_ids[first_title] = first_phase_id
    for phase in FIXTURE_SPEC["phases"][1:]:
        created = _api_json(
            teacher,
            "POST",
            f"/api/teaching/units/{unit_id}/phases",
            expected=(201,),
            body={"title": phase["title"]},
        )
        phase_ids[str(phase["title"])] = str(created["id"])

    module_ids: dict[str, str] = {}
    section_ids: dict[str, str] = {}
    task_ids: dict[str, str] = {}
    for phase, module in _iter_modules():
        created_module = _api_json(
            teacher,
            "POST",
            f"/api/teaching/units/{unit_id}/modules",
            expected=(201,),
            body={
                "title": module["title"],
                "phase_id": phase_ids[phase["title"]],
                "module_kind": module.get("module_kind", "learning"),
            },
        )
        module_id = str(created_module["id"])
        module_ids[module["key"]] = module_id
        target = _api_json(
            teacher,
            "GET",
            f"/api/teaching/units/{unit_id}/modules/{module_id}/content-target",
            expected=(200,),
        )
        section_id = str(target["section_id"])
        section_ids[module["key"]] = section_id
        _create_materials(teacher, unit_id=unit_id, section_id=section_id, module=module)
        for task in module["tasks"]:
            created_task = _api_json(
                teacher,
                "POST",
                f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
                expected=(201,),
                body=_task_payload(task, h5p_content_id=h5p_content_id),
            )
            task_ids[task["key"]] = str(created_task["id"])

    for source, target in FIXTURE_EDGES:
        _api_json(
            teacher,
            "POST",
            f"/api/teaching/units/{unit_id}/modules/edges",
            expected=(201,),
            body={"from_module_id": module_ids[source], "to_module_id": module_ids[target]},
        )
    for _, module in _iter_modules():
        required = int(module["required_prereq_count"])
        if required:
            _api_json(
                teacher,
                "PATCH",
                f"/api/teaching/units/{unit_id}/modules/{module_ids[module['key']]}",
                expected=(200,),
                body={"required_prereq_count": required},
            )

    course_module = _api_json(
        teacher,
        "POST",
        f"/api/teaching/courses/{course_id}/modules",
        expected=(201,),
        body={"unit_id": unit_id},
    )
    course_module_id = str(course_module["id"])
    for section_id in section_ids.values():
        _api_json(
            teacher,
            "PATCH",
            f"/api/teaching/courses/{course_id}/modules/{course_module_id}/sections/{section_id}/visibility",
            expected=(200,),
            body={"visible": True},
        )
    student_sub = student.subject()
    member_response = teacher.request(
        "POST",
        f"/api/teaching/courses/{course_id}/members",
        expected=(201, 204),
        json_body={"student_sub": student_sub},
    )
    _ = member_response

    submission = _api_json(
        student,
        "POST",
        f"/api/learning/courses/{course_id}/tasks/{task_ids['start_submission']}/submissions",
        expected=(202,),
        body={
            "intent": "submit",
            "kind": "text",
            "text_body": (
                "Ein digitales System nimmt Daten auf, verarbeitet sie nach festgelegten Regeln "
                "und erzeugt daraus eine Ausgabe."
            ),
        },
    )
    _wait_for_feedback(
        student,
        course_id=course_id,
        task_id=task_ids["start_submission"],
        submission_id=str(submission["id"]),
        timeout_seconds=config.ai_timeout_seconds,
    )

    dialog_session = _api_json(
        student,
        "POST",
        f"/api/learning/courses/{course_id}/tasks/{task_ids['dialog']}/dialog-sessions",
        expected=(200, 201),
    )
    dialog_session_id = str(dialog_session["id"])
    turn = _api_json(
        student,
        "POST",
        f"/api/learning/courses/{course_id}/tasks/{task_ids['dialog']}/dialog-sessions/{dialog_session_id}/turns",
        expected=(200,),
        headers={"Idempotency-Key": "dev-account-seed-turn"},
        body={
            "student_message_md": (
                "Ich möchte untersuchen, wie Eingaben die Ausgabe eines Systems beeinflussen."
            )
        },
    )
    turns = turn.get("turns") or []
    latest_turn = turns[-1] if turns else {}
    if latest_turn.get("status") != "completed" or not latest_turn.get("assistant_reply_md"):
        raise RuntimeError("dialog fixture failed: completed AI turn missing")

    state.update(
        {
            "status": "complete",
            "module_ids": module_ids,
            "section_ids": section_ids,
            "task_ids": task_ids,
            "dialog_session_id": dialog_session_id,
        }
    )
    write_state(config.state_path, state)
    return state


def upgrade_landscape_with_practice(
    config: DevConfig,
    *,
    teacher: BrowserSession,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Add the Practice fixture to the previous landscape without resetting learners.

    The authenticated teacher must own the recorded unit and course. Progress is
    stored after every created resource so an interrupted local upgrade can be
    resumed without duplicating modules or tasks.
    """

    upgraded = dict(state)
    upgraded.update({"status": "upgrading", "version": 3})
    module_ids = dict(upgraded.get("module_ids") or {})
    section_ids = dict(upgraded.get("section_ids") or {})
    task_ids = dict(upgraded.get("task_ids") or {})
    upgraded.update(
        {"module_ids": module_ids, "section_ids": section_ids, "task_ids": task_ids}
    )
    write_state(config.state_path, upgraded)

    unit_id = str(upgraded["unit_id"])
    course_id = str(upgraded["course_id"])
    phases = teacher.request(
        "GET",
        f"/api/teaching/units/{unit_id}/phases",
        expected=(200,),
    ).json()
    if not isinstance(phases, list):
        raise RuntimeError("Practice fixture upgrade failed: phase list missing")
    practice_phase = next(
        (phase for phase in phases if str(phase.get("title")) == "Erarbeitung"),
        None,
    )
    if practice_phase is None:
        raise RuntimeError("Practice fixture upgrade failed: target phase missing")
    practice_phase_id = str(practice_phase["id"])

    graph = _api_json(
        teacher,
        "GET",
        f"/api/teaching/units/{unit_id}/modules/graph",
        expected=(200,),
    )
    graph_modules = list(graph.get("modules") or [])
    course_modules = teacher.request(
        "GET",
        f"/api/teaching/courses/{course_id}/modules",
        expected=(200,),
    ).json()
    if not isinstance(course_modules, list):
        raise RuntimeError("Practice fixture upgrade failed: course module list missing")
    course_module = next(
        (item for item in course_modules if str(item.get("unit_id")) == unit_id),
        None,
    )
    if course_module is None:
        raise RuntimeError("Practice fixture upgrade failed: course module missing")
    course_module_id = str(course_module["id"])
    h5p_content_id = str(upgraded["h5p_content_id"])

    practice_modules = [
        module for _, module in _iter_modules() if module["key"] in PRACTICE_MODULE_KEYS
    ]
    for module in practice_modules:
        key = str(module["key"])
        module_id = str(module_ids.get(key) or "")
        if not module_id:
            existing = next(
                (
                    item
                    for item in graph_modules
                    if str(item.get("title")) == str(module["title"])
                    and str(item.get("module_kind") or "learning") == "practice"
                ),
                None,
            )
            if existing is None:
                existing = _api_json(
                    teacher,
                    "POST",
                    f"/api/teaching/units/{unit_id}/modules",
                    expected=(201,),
                    body={
                        "title": module["title"],
                        "phase_id": practice_phase_id,
                        "module_kind": "practice",
                    },
                )
                graph_modules.append(existing)
            module_id = str(existing["id"])
            module_ids[key] = module_id
            write_state(config.state_path, upgraded)

        target = _api_json(
            teacher,
            "GET",
            f"/api/teaching/units/{unit_id}/modules/{module_id}/content-target",
            expected=(200,),
        )
        section_id = str(target["section_id"])
        section_ids[key] = section_id
        for task in module["tasks"]:
            task_key = str(task["key"])
            if not str(task_ids.get(task_key) or ""):
                existing_tasks = teacher.request(
                    "GET",
                    f"/api/teaching/units/{unit_id}/modules/{module_id}/tasks",
                    expected=(200,),
                ).json()
                if not isinstance(existing_tasks, list):
                    raise RuntimeError("Practice fixture upgrade failed: task list missing")
                existing_task = next(
                    (
                        item
                        for item in existing_tasks
                        if str(item.get("kind")) == str(task["kind"])
                        and str(item.get("instruction_md")) == str(task["instruction_md"])
                    ),
                    None,
                )
                if existing_task is None:
                    existing_task = _api_json(
                        teacher,
                        "POST",
                        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
                        expected=(201,),
                        body=_task_payload(task, h5p_content_id=h5p_content_id),
                    )
                task_ids[task_key] = str(existing_task["id"])
                write_state(config.state_path, upgraded)

        _api_json(
            teacher,
            "PATCH",
            f"/api/teaching/units/{unit_id}/modules/{module_id}",
            expected=(200,),
            body={"required_prereq_count": int(module["required_prereq_count"])},
        )
        _api_json(
            teacher,
            "PATCH",
            f"/api/teaching/courses/{course_id}/modules/{course_module_id}/sections/{section_id}/visibility",
            expected=(200,),
            body={"visible": True},
        )
        write_state(config.state_path, upgraded)

    graph = _api_json(
        teacher,
        "GET",
        f"/api/teaching/units/{unit_id}/modules/graph",
        expected=(200,),
    )
    modules_in_target_phase = [
        str(item["id"])
        for item in graph.get("modules") or []
        if str(item.get("phase_id")) == practice_phase_id
        and str(item["id"]) not in {str(module_ids[key]) for key in PRACTICE_MODULE_KEYS}
    ]
    practice_ids = [str(module_ids[key]) for key in ("practice_native", "practice_h5p")]
    if any(
        str(item.get("phase_id")) != practice_phase_id
        for item in graph.get("modules") or []
        if str(item.get("id")) in practice_ids
    ):
        reordered = teacher.request(
            "POST",
            f"/api/teaching/units/{unit_id}/phases/{practice_phase_id}/modules/reorder",
            expected=(200,),
            json_body={"module_ids": modules_in_target_phase + practice_ids},
        ).json()
        if not isinstance(reordered, list):
            raise RuntimeError("Practice fixture upgrade failed: module reorder missing")

    for phase in phases:
        if str(phase.get("title")) == "Üben":
            teacher.request(
                "DELETE",
                f"/api/teaching/units/{unit_id}/phases/{phase['id']}",
                expected=(204,),
            )

    graph = _api_json(
        teacher,
        "GET",
        f"/api/teaching/units/{unit_id}/modules/graph",
        expected=(200,),
    )
    existing_edges = {
        (str(edge.get("from")), str(edge.get("to"))) for edge in graph.get("edges") or []
    }
    for source, target in FIXTURE_EDGES:
        if target not in PRACTICE_MODULE_KEYS:
            continue
        edge = (str(module_ids[source]), str(module_ids[target]))
        if edge not in existing_edges:
            _api_json(
                teacher,
                "POST",
                f"/api/teaching/units/{unit_id}/modules/edges",
                expected=(201,),
                body={"from_module_id": edge[0], "to_module_id": edge[1]},
            )

    upgraded["status"] = "complete"
    write_state(config.state_path, upgraded)
    return upgraded


def _sessions(
    config: DevConfig, credentials: dict[str, str]
) -> tuple[BrowserSession, BrowserSession]:
    teacher = BrowserSession(config)
    teacher.login(
        email=credentials["DEV_TEACHER_EMAIL"],
        password=credentials["DEV_TEACHER_PASSWORD"],
    )
    student = BrowserSession(config)
    student.login(
        email=credentials["DEV_STUDENT_EMAIL"],
        password=credentials["DEV_STUDENT_PASSWORD"],
    )
    return teacher, student


def _provision_identities(config: DevConfig, credentials: dict[str, str]) -> None:
    admin = KeycloakAdmin(config)
    token = admin.token()
    admin.ensure_user(
        token=token,
        email=credentials["DEV_TEACHER_EMAIL"],
        password=credentials["DEV_TEACHER_PASSWORD"],
        role="teacher",
        display_name="Dev-Lehrkraft",
    )
    admin.ensure_user(
        token=token,
        email=credentials["DEV_STUDENT_EMAIL"],
        password=credentials["DEV_STUDENT_PASSWORD"],
        role="student",
        display_name="Dev-Schüler",
    )


def ensure_command(config: DevConfig) -> None:
    """Provision missing local state and leave a complete fixture unchanged."""

    run_preflight(config)
    credentials = ensure_env_credentials(config.env_path)
    os.environ.update(credentials)
    _provision_identities(config, credentials)
    teacher, student = _sessions(config, credentials)
    state = read_state(config.state_path)
    fixture_courses = _owned_fixture_courses(teacher)
    decision = fixture_decision(state, course_count=len(fixture_courses))
    if decision == "ready":
        print(
            f"Dev-Accounts und modulare Testlandschaft sind bereit. Zugangsdaten: {config.env_path}"
        )
        return
    if decision == "upgrade":
        upgrade_landscape_with_practice(config, teacher=teacher, state=state or {})
        print(
            "Dev-Accounts und modulare Testlandschaft wurden um Übungsmodule ergänzt. "
            f"Zugangsdaten: {config.env_path}"
        )
        return
    if decision == "rebuild":
        run_product_storage_preflight(teacher)
        _delete_owned_data(
            teacher,
            timeout_seconds=config.ai_timeout_seconds,
            prior_state=state,
            state_path=config.state_path,
        )
        _delete_tool_h5p(teacher, state)
        config.state_path.unlink(missing_ok=True)
    elif decision == "explicit_reset":
        raise RuntimeError(
            "Existing GUSTAV Browser-Test has no complete tool state. "
            "Run 'make reset-dev-accounts' for an explicit rebuild."
        )
    create_landscape(config, teacher=teacher, student=student)
    print(
        f"Dev-Accounts und modulare Testlandschaft wurden angelegt. Zugangsdaten: {config.env_path}"
    )


def reset_command(config: DevConfig) -> None:
    """Reset only resources visible to the Dev teacher and tool-recorded H5P."""

    run_preflight(config)
    credentials = ensure_env_credentials(config.env_path)
    os.environ.update(credentials)
    _provision_identities(config, credentials)
    teacher, student = _sessions(config, credentials)
    previous_state = read_state(config.state_path)
    run_product_storage_preflight(teacher)
    _delete_owned_data(
        teacher,
        timeout_seconds=config.ai_timeout_seconds,
        prior_state=previous_state,
        state_path=config.state_path,
    )
    _delete_tool_h5p(teacher, previous_state)
    config.state_path.unlink(missing_ok=True)
    create_landscape(config, teacher=teacher, student=student)
    print(f"Dev-Daten wurden zurückgesetzt. Zugangsdaten: {config.env_path}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision local GUSTAV browser personas")
    parser.add_argument("command", choices=("ensure", "reset"))
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if not args.env_file.is_file():
            raise RuntimeError(f"local .env file missing: {args.env_file}")
        _load_dotenv(args.env_file)
        config = DevConfig.from_environment(env_path=args.env_file, state_path=args.state_file)
        if args.command == "ensure":
            ensure_command(config)
        else:
            reset_command(config)
        return 0
    except (RuntimeError, requests.RequestException) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
