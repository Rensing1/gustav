"""Run mutating browser acceptance tests only against the local GUSTAV stack.

Why:
    Feature acceptance exercises real authentication, application APIs and
    persistence. This orchestrator narrows each normal run to one requested
    spec and guarantees a best-effort owner-scoped cleanup on every exit path.

Security:
    Remote Web, Keycloak, Storage and PostgreSQL targets are rejected without
    an override. Cleanup is limited to exact Keycloak identities recorded in a
    private run manifest and to product data owned by those identities.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import urljoin, urlsplit

from backend.tools.dev_accounts import (
    BrowserSession,
    DevConfig,
    KeycloakAdmin,
    _delete_owned_data,
    _expect,
    _list_all,
    _list_course_catalog,
    _load_dotenv,
    _verify_option,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
E2E_DIR = FRONTEND_ROOT / "e2e"
STATE_PATH = PROJECT_ROOT / ".tmp" / "feature-acceptance-state.json"
LOCK_PATH = PROJECT_ROOT / ".tmp" / "feature-acceptance.lock"
FEATURE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCAL_HTTP_HOSTS = frozenset({"app.localhost", "id.localhost", "localhost", "127.0.0.1", "::1"})
LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "supabase_db_gustav-alpha2"})
RUNTIME_CONTAINERS = (
    "gustav-alpha2",
    "gustav-frontend",
    "gustav-h5p",
    "gustav-learning-worker",
)
RUNTIME_DATABASE_VARIABLES = {
    "gustav-alpha2": (
        "DATABASE_URL",
        "TEACHING_DATABASE_URL",
        "LEARNING_DATABASE_URL",
        "LEARNING_WORKER_DATABASE_URL",
        "SESSION_DATABASE_URL",
        "SERVICE_ROLE_DSN",
    ),
    "gustav-learning-worker": (
        "LEARNING_DATABASE_URL",
        "LEARNING_WORKER_DATABASE_URL",
    ),
}
PROFILE_MARKERS = {
    "acceptance": "@feature-acceptance",
    "detail": "@feature-detail",
}


def _require_local_url(value: str, *, label: str) -> None:
    parsed = urlsplit((value or "").strip())
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme not in {"http", "https"}
        or host not in LOCAL_HTTP_HOSTS
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise RuntimeError(f"{label} must use the local GUSTAV stack")


def _require_local_database(value: str) -> None:
    parsed = urlsplit((value or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"postgres", "postgresql"} or host not in LOCAL_DATABASE_HOSTS:
        raise RuntimeError("E2E database must be the local Supabase database")


def _assert_runtime_stack_safe(
    environments: dict[str, dict[str, str]],
) -> None:
    """Validate the effective environment of every already-running service.

    Reading ``.env`` is insufficient: Docker keeps the values with which a
    container was created. A later local edit must therefore never make an old
    remote container look safe to this process.
    """

    for container in RUNTIME_CONTAINERS:
        environment = environments.get(container)
        if environment is None:
            raise RuntimeError(f"required local container is not running: {container}")
        if environment.get("GUSTAV_ENV", "dev").strip().lower() in {
            "prod",
            "production",
        }:
            raise RuntimeError(f"{container} uses a production environment")

    url_variables = {
        "gustav-alpha2": ("WEB_BASE", "KC_PUBLIC_BASE_URL"),
        "gustav-frontend": ("ORIGIN", "KC_PUBLIC_BASE_URL"),
        "gustav-learning-worker": ("WEB_BASE",),
    }
    for container, variables in url_variables.items():
        for variable in variables:
            value = environments[container].get(variable, "")
            try:
                _require_local_url(value, label=variable)
            except RuntimeError as exc:
                raise RuntimeError(f"{container} has unsafe {variable}") from exc

    for container, variables in RUNTIME_DATABASE_VARIABLES.items():
        for variable in variables:
            value = environments[container].get(variable, "")
            try:
                _require_local_database(value)
            except RuntimeError as exc:
                raise RuntimeError(f"{container} has unsafe {variable}") from exc


def _inspect_runtime_environments() -> dict[str, dict[str, str]]:
    """Read effective container settings without invoking a shell."""

    environments: dict[str, dict[str, str]] = {}
    for container in RUNTIME_CONTAINERS:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{json .Config.Env}}", container],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"required local container is not running: {container}")
        try:
            entries = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"could not inspect local container: {container}") from exc
        if not isinstance(entries, list):
            raise RuntimeError(f"could not inspect local container: {container}")
        environment: dict[str, str] = {}
        for entry in entries:
            if isinstance(entry, str) and "=" in entry:
                key, value = entry.split("=", 1)
                environment[key] = value
        environments[container] = environment
    return environments


@dataclass(frozen=True)
class FeatureAcceptanceConfig:
    """Safety-critical environment values needed before any browser mutation."""

    web_base: str
    kc_base: str
    storage_base: str
    database_url: str
    environment: str
    mutation_allowed: str

    @classmethod
    def from_environment(cls) -> "FeatureAcceptanceConfig":
        return cls(
            web_base=(os.getenv("WEB_BASE") or "https://app.localhost").rstrip("/"),
            kc_base=(
                os.getenv("KC_BASE") or os.getenv("KC_PUBLIC_BASE_URL") or "https://id.localhost"
            ).rstrip("/"),
            storage_base=(os.getenv("SUPABASE_URL") or "http://127.0.0.1:54321").rstrip("/"),
            database_url=(
                os.getenv("E2E_DATABASE_URL") or os.getenv("SESSION_DATABASE_URL") or ""
            ).strip(),
            environment=(os.getenv("GUSTAV_ENV") or "dev").strip().lower(),
            mutation_allowed=(os.getenv("E2E_LOCAL_MUTATION_ALLOWED") or "").strip(),
        )

    def assert_safe(self) -> None:
        """Fail closed unless every mutable service is unmistakably local."""

        if self.mutation_allowed != "1":
            raise RuntimeError(
                "E2E_LOCAL_MUTATION_ALLOWED=1 is required for mutating browser tests"
            )
        if self.environment in {"prod", "production"}:
            raise RuntimeError("feature acceptance is forbidden in production")
        _require_local_url(self.web_base, label="WEB_BASE")
        _require_local_url(self.kc_base, label="KC_BASE")
        _require_local_url(self.storage_base, label="SUPABASE_URL")
        _require_local_database(self.database_url)


def validate_feature_name(
    value: str, *, profile: str = "acceptance", e2e_dir: Path = E2E_DIR
) -> Path:
    """Resolve a safe spec stem without accepting arbitrary filesystem paths."""

    if not FEATURE_PATTERN.fullmatch(value or ""):
        raise RuntimeError(
            "FEATURE must be a non-empty lowercase spec name such as learner-navigation"
        )
    spec = e2e_dir / f"{value}.spec.ts"
    if not spec.is_file():
        raise RuntimeError(f"unknown FEATURE: {value}")
    marker = PROFILE_MARKERS.get(profile)
    if marker is None:
        raise RuntimeError(f"unknown feature test profile: {profile}")
    if marker not in spec.read_text(encoding="utf-8"):
        raise RuntimeError(f"FEATURE has no {marker} test: {value}")
    return spec


def build_playwright_command(
    *,
    feature: str | None,
    all_features: bool,
    profile: str = "acceptance",
    e2e_dir: Path = E2E_DIR,
) -> list[str]:
    """Build the fixed Playwright command for one spec or the opt-in regression."""

    marker = PROFILE_MARKERS.get(profile)
    if marker is None:
        raise RuntimeError(f"unknown feature test profile: {profile}")
    command = ["npm", "run", "test:e2e", "--"]
    if all_features:
        command.extend(["--grep", marker])
        return command
    spec = validate_feature_name(feature or "", profile=profile, e2e_dir=e2e_dir)
    command.extend([str(spec), "--grep", marker])
    return command


def _dev_config(config: FeatureAcceptanceConfig) -> DevConfig:
    return DevConfig(
        env_path=PROJECT_ROOT / ".env",
        state_path=STATE_PATH,
        web_base=config.web_base,
        kc_base=config.kc_base,
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
        storage_base=config.storage_base,
        openai_base="https://unused.invalid",
        openai_api_key="",
        ai_text_model="",
        verify=_verify_option(),
        timeout_seconds=float(os.getenv("E2E_CLEANUP_TIMEOUT_SECONDS", "30")),
        ai_timeout_seconds=1,
    )


def _read_state(path: Path | None = None) -> dict[str, Any] | None:
    path = path or STATE_PATH
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") not in {1, 2}:
        raise RuntimeError("feature acceptance state manifest is invalid")
    if payload.get("version") == 1:
        legacy_h5p = payload.get("h5p_content_ids", [])
        if legacy_h5p:
            raise RuntimeError(
                "feature acceptance state has ownerless H5P contents and requires manual review"
            )
        payload = {
            **payload,
            "version": 2,
            "h5p_contents": [],
            "worker_pause_requested": False,
        }
        payload.pop("h5p_content_ids", None)
    return payload


def _write_state(state: dict[str, Any], path: Path | None = None) -> None:
    path = path or STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    os.replace(temporary, path)
    path.chmod(0o600)


def _user_is_owned(user: dict[str, Any], *, run_id: str) -> bool:
    email = str(user.get("email") or "").lower()
    role = str(user.get("role") or "")
    marker = f".e2e-{run_id}@"
    return role in {"teacher", "student"} and marker in email


def _keycloak_user_id(admin: KeycloakAdmin, token: str, email: str) -> str | None:
    base = f"{admin.config.kc_base}/admin/realms/{admin.config.realm}"
    response = _expect(
        admin.session.get(
            f"{base}/users",
            headers=admin._headers(token),
            params={"email": email, "exact": "true"},
            timeout=admin.config.timeout_seconds,
        ),
        {200},
        action="Keycloak E2E user lookup",
    )
    users = response.json()
    if not isinstance(users, list) or not users:
        return None
    return str(users[0].get("id") or "") or None


def _reset_password(admin: KeycloakAdmin, token: str, *, user_id: str, password: str) -> None:
    base = f"{admin.config.kc_base}/admin/realms/{admin.config.realm}"
    _expect(
        admin.session.put(
            f"{base}/users/{user_id}/reset-password",
            headers=admin._headers(token),
            json={"type": "password", "value": password, "temporary": False},
            timeout=admin.config.timeout_seconds,
        ),
        {200, 204},
        action="Keycloak E2E password reset",
    )


def _delete_user(admin: KeycloakAdmin, token: str, *, user_id: str) -> None:
    base = f"{admin.config.kc_base}/admin/realms/{admin.config.realm}"
    _expect(
        admin.session.delete(
            f"{base}/users/{user_id}",
            headers=admin._headers(token),
            timeout=admin.config.timeout_seconds,
        ),
        {204, 404},
        action="Keycloak E2E user deletion",
    )


def _revoke_cli_tokens(session: BrowserSession) -> None:
    """Revoke tokens through the authenticated profile's product action.

    The public proxy sends ``/api/*`` directly to FastAPI, while CLI-token
    routes require the Browser-BFF bearer session. The profile page is the
    stable product boundary that owns this operation and already forwards the
    correct bearer token without exposing it to this cleanup process.
    """

    profile = _expect(
        session.session.get(
            f"{session.config.web_base}/profile",
            allow_redirects=True,
            timeout=session.config.timeout_seconds,
        ),
        {200},
        action="E2E profile token listing",
    )
    token_ids = set(
        re.findall(
            r'name=["\']token_id["\'][^>]*value=["\']([0-9a-fA-F-]{36})["\']',
            profile.text,
        )
    )
    action_url = urljoin(profile.url, "?/revokeCliToken")
    headers = {"Origin": session.config.web_base, "Referer": profile.url}
    for token_id in sorted(token_ids):
        if not re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
            r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}",
            token_id,
        ):
            raise RuntimeError("CLI token cleanup refused an invalid token id")
        _expect(
            session.session.post(
                action_url,
                data={"token_id": token_id},
                headers=headers,
                allow_redirects=True,
                timeout=session.config.timeout_seconds,
            ),
            {200},
            action="E2E CLI token revocation",
        )


def _delete_registered_h5p_contents(session: BrowserSession, content_ids: list[str]) -> None:
    """Delete only exact H5P ids recorded by the active private manifest."""

    headers = {
        "Origin": session.config.web_base,
        "Referer": f"{session.config.web_base}/h5p/editor",
    }
    for content_id in content_ids:
        _expect(
            session.session.delete(
                f"{session.config.web_base}/h5p/contents/{content_id}",
                headers=headers,
                timeout=session.config.timeout_seconds,
            ),
            {204, 404},
            action="registered E2E H5P cleanup",
        )


def _jwt_subject(token: str) -> str | None:
    """Read a JWT subject for exact cleanup matching without verifying or logging it.

    Signature verification is unnecessary here because the token is never
    trusted for authorization. It is only used to narrow deletion of rows from
    the already local, privileged session store to known Keycloak subjects.
    """

    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    subject = decoded.get("sub") if isinstance(decoded, dict) else None
    return subject if isinstance(subject, str) and subject else None


def _bff_session_ids_for_subjects(
    rows: Sequence[tuple[Any, Any, Any]], user_ids: set[str]
) -> list[str]:
    """Return only opaque session ids whose access or ID token has an exact subject."""

    return [
        str(session_id)
        for session_id, access_token, id_token in rows
        if _jwt_subject(str(id_token or "")) in user_ids
        or _jwt_subject(str(access_token or "")) in user_ids
    ]


def _delete_run_sessions(database_url: str, user_ids: set[str]) -> None:
    """Delete exact app and BFF sessions belonging to resolved run identities."""

    if not user_ids:
        return
    _require_local_database(database_url)
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select session_id, access_token, id_token from public.bff_sessions")
            bff_session_ids = _bff_session_ids_for_subjects(cursor.fetchall(), user_ids)
            cursor.execute(
                "delete from public.app_sessions where sub = any(%s)",
                (sorted(user_ids),),
            )
            if bff_session_ids:
                cursor.execute(
                    "delete from public.bff_sessions where session_id = any(%s)",
                    (sorted(set(bff_session_ids)),),
                )
            cursor.execute(
                "select count(*) from public.app_sessions where sub = any(%s)",
                (sorted(user_ids),),
            )
            if int(cursor.fetchone()[0]) != 0:
                raise RuntimeError("run-owned application sessions remain")
            cursor.execute("select session_id, access_token, id_token from public.bff_sessions")
            remaining = cursor.fetchall()
            if _bff_session_ids_for_subjects(remaining, user_ids):
                raise RuntimeError("run-owned BFF sessions remain")


def _restore_realm_smtp(admin: KeycloakAdmin, token: str, smtp_server: dict[str, str]) -> None:
    """Restore the exact pre-test SMTP representation recorded in the manifest."""

    base = f"{admin.config.kc_base}/admin/realms/{admin.config.realm}"
    current_response = _expect(
        admin.session.get(
            base,
            headers=admin._headers(token),
            timeout=admin.config.timeout_seconds,
        ),
        {200},
        action="Keycloak realm SMTP recovery lookup",
    )
    current = current_response.json()
    if not isinstance(current, dict):
        raise RuntimeError("Keycloak realm response is invalid")
    _expect(
        admin.session.put(
            base,
            headers=admin._headers(token),
            json={**current, "smtpServer": smtp_server},
            timeout=admin.config.timeout_seconds,
        ),
        {200, 204},
        action="Keycloak realm SMTP recovery",
    )


def _worker_is_paused() -> bool:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Paused}}", "gustav-learning-worker"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("could not inspect local learning worker")
    value = result.stdout.strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError("local learning worker returned an invalid pause state")
    return value == "true"


def _set_worker_paused(paused: bool, *, path: Path | None = None) -> None:
    """Pause provider execution with recoverable intent in the private manifest."""

    path = path or STATE_PATH
    state = _read_state(path)
    if state is None:
        raise RuntimeError("feature acceptance state manifest is missing")
    if paused:
        state["worker_pause_requested"] = True
        _write_state(state, path)
        if not _worker_is_paused():
            result = subprocess.run(["docker", "pause", "gustav-learning-worker"], check=False)
            if result.returncode != 0:
                raise RuntimeError("could not pause local learning worker")
        return
    if _worker_is_paused():
        result = subprocess.run(["docker", "unpause", "gustav-learning-worker"], check=False)
        if result.returncode != 0:
            raise RuntimeError("could not unpause local learning worker")
    state["worker_pause_requested"] = False
    _write_state(state, path)


def _complete_queued_feedback(
    config: FeatureAcceptanceConfig,
    *,
    course_id: str,
    task_id: str,
    student_sub: str,
) -> None:
    """Replace only provider output for one existing locally queued submission.

    The browser and application must already have created both the submission
    and its queue row. This adapter applies the same worker completion helper
    and practice scheduler used in production, then removes that exact job.
    """

    try:
        course_uuid = str(uuid.UUID(course_id))
        task_uuid = str(uuid.UUID(task_id))
    except ValueError as exc:
        raise RuntimeError("deterministic feedback requires valid course and task ids") from exc
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", student_sub or ""):
        raise RuntimeError("deterministic feedback requires a valid learner subject")

    _require_local_database(config.database_url)
    import psycopg
    from psycopg.rows import dict_row

    from backend.learning.practice.completion import complete_worker_practice_attempt

    with psycopg.connect(config.database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            deadline = time.monotonic() + float(
                os.getenv("E2E_FEEDBACK_QUEUE_TIMEOUT_SECONDS", "15")
            )
            rows: list[dict[str, Any]] = []
            while not rows and time.monotonic() < deadline:
                cursor.execute(
                    """
                    select submission.id::text as submission_id,
                           submission.text_body,
                           job.id::text as job_id,
                           job.payload
                      from public.learning_submissions submission
                      join public.learning_submission_jobs job
                        on job.submission_id = submission.id
                     where submission.course_id = %s::uuid
                       and submission.task_id = %s::uuid
                       and submission.student_sub = %s
                       and submission.intent = 'feedback'
                       and submission.analysis_status in ('pending', 'extracted')
                       and job.status in ('queued', 'leased')
                     order by submission.created_at desc, submission.id desc
                     limit 2
                     for update of submission, job
                    """,
                    (course_uuid, task_uuid, student_sub),
                )
                rows = cursor.fetchall()
                if not rows:
                    connection.rollback()
                    time.sleep(0.2)
            if len(rows) != 1:
                raise RuntimeError(
                    "deterministic feedback requires exactly one queued browser submission"
                )
            row = rows[0]
            payload = row["payload"] if isinstance(row["payload"], dict) else {}
            criteria = payload.get("criteria") if isinstance(payload, dict) else []
            criteria = criteria if isinstance(criteria, list) else []
            analysis_json = {
                "schema": "criteria.v2",
                "criteria_results": [
                    {
                        "criterion": str(criterion),
                        "score": 8,
                        "max_score": 10,
                        "feedback": "Das Kriterium ist nachvollziehbar erfüllt.",
                    }
                    for criterion in criteria
                ],
            }
            feedback = (
                "Die Antwort erklärt den Gedanken nachvollziehbar und kann jetzt "
                "weiterverwendet werden."
            )
            cursor.execute(
                """
                select public.learning_worker_update_completed(
                    %s::uuid, %s, %s, %s::jsonb
                )
                """,
                (
                    row["submission_id"],
                    row["text_body"],
                    feedback,
                    json.dumps(analysis_json),
                ),
            )
        complete_worker_practice_attempt(
            conn=connection,
            submission_id=str(row["submission_id"]),
            analysis_json=analysis_json,
            feedback_md=feedback,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.learning_submission_jobs where id = %s::uuid",
                (row["job_id"],),
            )
            cursor.execute(
                "select analysis_status from public.learning_submissions where id = %s::uuid",
                (row["submission_id"],),
            )
            status = cursor.fetchone()
            if not status or status["analysis_status"] != "completed":
                raise RuntimeError("deterministic feedback completion was not persisted")


def _assert_owned_product_data_empty(session: BrowserSession) -> None:
    """Confirm the run-owned teacher has no remaining courses or units."""

    remaining = (
        _list_course_catalog(session, status="active")
        + _list_course_catalog(session, status="archived")
        + _list_all(session, "/api/teaching/units", page_size=100)
    )
    if remaining:
        raise RuntimeError("feature acceptance cleanup left run-owned product data")


def cleanup_manifest(
    config: FeatureAcceptanceConfig,
    *,
    keep_manifest: bool = False,
    path: Path | None = None,
) -> None:
    """Remove only data and identities recorded for one exact local E2E run."""

    path = path or STATE_PATH
    state = _read_state(path)
    if state is None:
        return
    run_id = str(state.get("run_id") or "")
    users = state.get("users")
    h5p_contents = state.get("h5p_contents", [])
    smtp_restore = state.get("keycloak_smtp_restore")
    worker_pause_requested = state.get("worker_pause_requested", False)
    if not re.fullmatch(r"[0-9a-f]{12}", run_id) or not isinstance(users, list):
        raise RuntimeError("feature acceptance state manifest has unsafe ownership data")
    if any(not isinstance(user, dict) or not _user_is_owned(user, run_id=run_id) for user in users):
        raise RuntimeError("feature acceptance cleanup refused a foreign identity")
    for user in users:
        keycloak_id = user.get("keycloak_id")
        if keycloak_id is not None and not re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}", str(keycloak_id)
        ):
            raise RuntimeError("feature acceptance state has an invalid Keycloak id")
    teacher_emails = {str(user["email"]).lower() for user in users if user.get("role") == "teacher"}
    if not isinstance(h5p_contents, list):
        raise RuntimeError("feature acceptance cleanup refused invalid H5P ownership data")
    for content in h5p_contents:
        if (
            not isinstance(content, dict)
            or not re.fullmatch(r"[1-9][0-9]*", str(content.get("content_id") or ""))
            or str(content.get("owner_email") or "").lower() not in teacher_emails
        ):
            raise RuntimeError("feature acceptance cleanup refused invalid H5P ownership data")
    if smtp_restore is not None and (
        not isinstance(smtp_restore, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in smtp_restore.items()
        )
    ):
        raise RuntimeError("feature acceptance cleanup refused invalid SMTP recovery data")
    if not isinstance(worker_pause_requested, bool):
        raise RuntimeError("feature acceptance cleanup refused invalid worker recovery data")

    password = (os.getenv("E2E_TEST_PASSWORD") or "").strip()
    if users and not password:
        raise RuntimeError("E2E_TEST_PASSWORD is required for cleanup")
    dev_config = _dev_config(config)
    admin = KeycloakAdmin(dev_config)
    needs_admin = bool(users) or smtp_restore is not None
    token = admin.token() if needs_admin else ""
    resolved: list[tuple[dict[str, Any], str, bool]] = []
    errors: list[str] = []

    if worker_pause_requested:
        try:
            _set_worker_paused(False, path=path)
            state["worker_pause_requested"] = False
        except Exception as exc:
            errors.append(f"learning worker recovery: {exc}")

    if smtp_restore is not None:
        try:
            _restore_realm_smtp(admin, token, smtp_restore)
            state.pop("keycloak_smtp_restore", None)
            _write_state(state, path)
        except Exception as exc:
            errors.append(f"Keycloak SMTP recovery: {exc}")

    for user in users:
        email = str(user["email"])
        try:
            discovered_id = _keycloak_user_id(admin, token, email)
            recorded_id = str(user.get("keycloak_id") or "") or None
            if discovered_id and recorded_id and discovered_id != recorded_id:
                raise RuntimeError("recorded Keycloak id does not match the exact email lookup")
            user_id = discovered_id or recorded_id
            if user_id:
                resolved.append((user, user_id, discovered_id is not None))
        except Exception as exc:  # Cleanup continues so every owned identity is attempted.
            errors.append(f"{email}: {exc}")

    h5p_by_owner: dict[str, list[str]] = {}
    for content in h5p_contents:
        h5p_by_owner.setdefault(str(content["owner_email"]).lower(), []).append(
            str(content["content_id"])
        )
    for user, user_id, present in resolved:
        if user.get("role") != "teacher":
            continue
        email = str(user["email"])
        if not present:
            if h5p_by_owner.get(email.lower()):
                errors.append(f"{email}: owned H5P contents require the recorded teacher")
            continue
        try:
            _reset_password(admin, token, user_id=user_id, password=password)
            session = BrowserSession(dev_config)
            session.login(email=email, password=password)
            _revoke_cli_tokens(session)
            owner_h5p = list(dict.fromkeys(h5p_by_owner.pop(email.lower(), [])))
            if owner_h5p:
                _delete_registered_h5p_contents(session, owner_h5p)
            _delete_owned_data(
                session,
                timeout_seconds=float(os.getenv("E2E_DELETION_TIMEOUT_SECONDS", "120")),
            )
            _assert_owned_product_data_empty(session)
        except Exception as exc:
            errors.append(f"{email}: {exc}")

    if h5p_by_owner:
        errors.append("registered H5P contents could not be cleaned by their exact owner")

    try:
        _delete_run_sessions(config.database_url, {user_id for _, user_id, _ in resolved})
    except Exception as exc:
        errors.append(f"run-owned session cleanup: {exc}")

    if not errors and not keep_manifest:
        for user, user_id, _ in reversed(resolved):
            try:
                _delete_user(admin, token, user_id=user_id)
                if _keycloak_user_id(admin, token, str(user["email"])) is not None:
                    raise RuntimeError("Keycloak E2E user still exists after deletion")
            except Exception as exc:
                errors.append(f"{user['email']}: {exc}")

    if errors:
        raise RuntimeError("feature acceptance cleanup failed: " + "; ".join(errors))
    if keep_manifest:
        _write_state(
            {
                "version": 2,
                "run_id": run_id,
                "users": users,
                "h5p_contents": [],
                "worker_pause_requested": False,
            },
            path,
        )
    else:
        path.unlink(missing_ok=True)
        print(
            "Feature acceptance cleanup confirmed: no run-owned users, courses, "
            "units, sessions, tokens or registered H5P contents remain."
        )


@contextmanager
def _exclusive_lock(path: Path | None = None) -> Iterator[None]:
    path = path or LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another feature acceptance run is already active") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_acceptance(*, feature: str | None, all_features: bool, profile: str = "acceptance") -> int:
    """Validate, execute and clean one local acceptance run."""

    command = build_playwright_command(
        feature=feature,
        all_features=all_features,
        profile=profile,
        e2e_dir=E2E_DIR,
    )
    if (PROJECT_ROOT / ".env").is_file():
        _load_dotenv(PROJECT_ROOT / ".env")
    config = FeatureAcceptanceConfig.from_environment()
    config.assert_safe()
    _assert_runtime_stack_safe(_inspect_runtime_environments())
    password = (os.getenv("E2E_TEST_PASSWORD") or "").strip()
    if not password:
        raise RuntimeError("E2E_TEST_PASSWORD must be set in the ignored local .env")
    with _exclusive_lock():
        # A previous hard interruption may have skipped its finally block.
        cleanup_manifest(config)
        run_id = uuid.uuid4().hex[:12]
        _write_state(
            {
                "version": 2,
                "run_id": run_id,
                "users": [],
                "h5p_contents": [],
                "worker_pause_requested": False,
            }
        )
        child_environment = os.environ.copy()
        child_environment.update(
            {
                "E2E_RUN_ID": run_id,
                "E2E_STATE_PATH": str(STATE_PATH),
                "NODE_EXTRA_CA_CERTS": str(PROJECT_ROOT / ".tmp" / "caddy-root.crt"),
            }
        )
        exit_code = 1
        cleanup_error: Exception | None = None
        try:
            browser_check = subprocess.run(
                ["node", "tooling/check-playwright-browser.mjs", "chromium", "webkit"],
                cwd=FRONTEND_ROOT,
                env=child_environment,
                check=False,
            )
            if browser_check.returncode != 0:
                return browser_check.returncode
            exit_code = subprocess.run(
                command,
                cwd=FRONTEND_ROOT,
                env=child_environment,
                check=False,
            ).returncode
        finally:
            try:
                cleanup_manifest(config)
            except Exception as exc:
                cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error
        return exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local feature acceptance safely")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    selection = run.add_mutually_exclusive_group(required=True)
    selection.add_argument("--feature")
    selection.add_argument("--all", action="store_true", dest="all_features")
    run.add_argument("--profile", choices=tuple(PROFILE_MARKERS), default="acceptance")
    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--keep-manifest", action="store_true")
    worker = subparsers.add_parser("worker")
    worker.add_argument("action", choices=("hold", "release"))
    feedback = subparsers.add_parser("complete-feedback")
    feedback.add_argument("--course-id", required=True)
    feedback.add_argument("--task-id", required=True)
    feedback.add_argument("--student-sub", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--feature", required=True)
    validate.add_argument("--profile", choices=tuple(PROFILE_MARKERS), default="acceptance")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            validate_feature_name(args.feature, profile=args.profile)
            return 0
        if args.command == "run":
            return run_acceptance(
                feature=args.feature,
                all_features=args.all_features,
                profile=args.profile,
            )
        if (PROJECT_ROOT / ".env").is_file():
            _load_dotenv(PROJECT_ROOT / ".env")
        config = FeatureAcceptanceConfig.from_environment()
        config.assert_safe()
        _assert_runtime_stack_safe(_inspect_runtime_environments())
        if args.command == "cleanup":
            cleanup_manifest(config, keep_manifest=args.keep_manifest)
            return 0
        if args.command == "worker":
            _set_worker_paused(args.action == "hold")
            return 0
        if args.command == "complete-feedback":
            _complete_queued_feedback(
                config,
                course_id=args.course_id,
                task_id=args.task_id,
                student_sub=args.student_sub,
            )
            return 0
        raise RuntimeError("unknown feature acceptance command")
    except RuntimeError as exc:
        print(f"Feature acceptance refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
