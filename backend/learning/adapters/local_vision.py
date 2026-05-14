"""
Learning vision adapter (DSPy-only OCR over OpenAI-compatible endpoint).

Intent:
    Turn non-text submissions (image/PDF) into Markdown text via DSPy, so the
    worker can run the text feedback pipeline on a consistent representation.

Design:
    - DSPy-only: no direct Ollama client calls, no Python prompt templates.
    - Thread-safe: the worker may process jobs concurrently; use `dspy.context(...)`.

Security:
    - Do not log extracted OCR text or raw submission bytes.
"""

from __future__ import annotations

import os
import ipaddress
import socket
from typing import Dict, Optional
import base64
import logging
from urllib.parse import urlparse as _urlparse

from backend.learning.adapters.ports import (
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)
from backend.learning.adapters.dspy import helpers as dspy_helpers
from backend.vision.pipeline import stitch_images_vertically, process_pdf_bytes
from backend.storage.config import get_submissions_bucket, get_learning_max_upload_bytes
from backend.storage.mime_types import FILIUS_FLS_MIME, JPEG_MIME, MAKECODE_HEX_MIME, PDF_MIME, PNG_MIME, SCRATCH_SB3_MIME
from backend.storage.submission_content_signatures import validate_submission_content_signature

LOG = logging.getLogger(__name__)

SUPPORTED_MIME = {JPEG_MIME, PNG_MIME, PDF_MIME, SCRATCH_SB3_MIME, MAKECODE_HEX_MIME, FILIUS_FLS_MIME}
_LOCAL_HTTP_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}

def _require_secure_openai_base_url(base_url: str) -> None:
    """
    Historical security guard (now disabled).

    We intentionally do not block non-HTTPS OpenAI endpoints anymore. Operators
    may route traffic through VPNs (e.g. Tailscale) and accept responsibility
    for transport security at the network layer.
    """
    return


def _is_local_host(host: str) -> bool:
    """
    Return True if host resolves to loopback/private.

    Why:
        The learning worker must talk to Supabase Storage over HTTP in local
        and Docker-Compose setups, but service-role credentials must never be
        sent to arbitrary remote hosts. This helper classifies a host as
        "local" when it clearly resides on loopback/private networks.

    Behavior:
        - Explicit allowlist for common local hostnames.
        - Direct IPs: accept loopback/private ranges.
        - Hostnames (including `.local`):
            * Resolve via DNS and accept only when all resolved addresses
              are loopback/private.
    """
    host = (host or "").strip().lower()
    if not host:
        return False
    if host in _LOCAL_HTTP_HOSTS:
        return True
    try:
        # Direct IP literal
        parsed_ip = ipaddress.ip_address(host)
        return bool(parsed_ip.is_loopback or parsed_ip.is_private)
    except ValueError:
        # Not an IP literal: attempt DNS resolution and require all results
        # to be loopback/private. Fail closed on unexpected errors.
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            return False
        if not infos:
            return False
        for family, _socktype, _proto, _canonname, sockaddr in infos:
            try:
                if family == socket.AF_INET:
                    ip_str = sockaddr[0]
                elif family == socket.AF_INET6:
                    ip_str = sockaddr[0]
                else:
                    # Ignore non-IP families conservatively.
                    return False
                parsed = ipaddress.ip_address(ip_str)
                if not (parsed.is_loopback or parsed.is_private):
                    return False
            except Exception:
                return False
        return True


def _submissions_bucket() -> str:
    return get_submissions_bucket()


def _strip_bucket_prefix(key: str, bucket: str) -> str:
    prefix = f"{bucket}/"
    if key.startswith(prefix):
        return key[len(prefix) :]
    return key


def _storage_base_and_hosts() -> tuple[str | None, set[str]]:
    """
    Resolve Supabase base URL and allowed host:port combinations.

    Returns:
        tuple[str | None, set[str]]: (base_url, {"host:port", ...})
    """
    hosts: set[str] = set()
    base_url: str | None = None
    for env_name in ("SUPABASE_URL", "SUPABASE_PUBLIC_URL"):
        raw = (os.getenv(env_name) or "").strip()
        if not raw:
            continue
        try:
            parsed = _urlparse(raw)
        except Exception:
            continue
        scheme = (parsed.scheme or "").lower()
        host = (parsed.hostname or "").lower()
        if not host or scheme not in {"http", "https"}:
            continue
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80
        hosts.add(f"{host}:{port}")
        candidate = raw.rstrip("/")
        if base_url is None or env_name == "SUPABASE_URL":
            base_url = candidate
    return (base_url.rstrip("/") if base_url else None, hosts)


def _log_storage_event(*, submission_id: str, action: str, level: int = logging.INFO, **fields: object) -> None:
    """Emit sanitized Vision storage logs without leaking storage paths or PII."""
    safe_submission = submission_id or "unknown"
    parts = [f"learning.vision.storage action={action} submission_id={safe_submission}"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    LOG.log(level, " ".join(parts))


def _download_supabase_object(*, bucket: str, object_key: str, srk: str, max_bytes: int) -> tuple[bytes | None, str]:
    base_url, allowed_host_ports = _storage_base_and_hosts()
    if not base_url or not allowed_host_ports:
        return (None, "untrusted_host")
    object_path = object_key.lstrip("/")
    target = f"{base_url.rstrip('/')}/storage/v1/object/{bucket}/{object_path}"
    try:
        parsed = _urlparse(target)
    except Exception:
        return (None, "untrusted_host")
    host = (parsed.hostname or "").lower()
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return (None, "untrusted_host")
    if scheme == "http" and not _is_local_host(host):
        return (None, "untrusted_host")
    port = parsed.port or (443 if scheme == "https" else 80)
    host_port = f"{host}:{port}"
    if host_port not in allowed_host_ports:
        return (None, "untrusted_host")
    try:
        import httpx  # type: ignore
    except Exception:
        return (None, "http_client_unavailable")
    try:
        headers = {"apikey": srk, "Authorization": f"Bearer {srk}"}
        with httpx.Client(timeout=10, follow_redirects=False) as client:  # type: ignore[attr-defined]
            with client.stream("GET", target, headers=headers) as resp:
                code = int(getattr(resp, "status_code", 500))
                if 300 <= code < 400:
                    return (None, f"redirect:{code}")
                if code >= 400:
                    return (None, f"http_error:{code}")
                data = bytearray()
                for chunk in resp.iter_bytes():  # type: ignore[attr-defined]
                    if not chunk:
                        continue
                    data.extend(chunk)
                    if max_bytes > 0 and len(data) > max_bytes:
                        return (None, "size_exceeded")
        return (bytes(data), "ok")
    except Exception:
        return (None, "download_error")


def _remote_fetch_submission_object(
    *,
    bucket: str,
    object_key: str,
    srk: str,
    max_bytes: int,
    submission_id: str,
    success_action: str,
) -> Optional[bytes]:
    """Download a Supabase object with storage-role credentials and log outcome."""
    fetched, reason = _download_supabase_object(
        bucket=bucket,
        object_key=object_key,
        srk=srk,
        max_bytes=max_bytes,
    )
    if reason == "untrusted_host":
        raise VisionTransientError("untrusted_host")
    if reason == "size_exceeded":
        raise VisionTransientError("remote_fetch_too_large")
    if fetched:
        _log_storage_event(
            submission_id=submission_id,
            action=success_action,
            size=len(fetched),
        )
        return fetched
    if reason and reason != "ok":
        _log_storage_event(
            submission_id=submission_id,
            action="remote_fetch_failed",
            reason=reason,
        )
        raise VisionTransientError("remote_fetch_failed")
    return None


def _load_local_storage_bytes(
    *,
    root: str,
    storage_key: str,
    size_bytes: object,
    sha256_hex: object,
) -> Optional[bytes]:
    """Read bytes from STORAGE_VERIFY_ROOT after path, size and hash checks."""
    if not root or not storage_key:
        return None
    try:
        from pathlib import Path

        base = Path(root).resolve()
        target = (base / storage_key).resolve()
        common = os.path.commonpath([str(base), str(target)])
    except Exception:
        raise VisionPermanentError("path_error")
    if common != str(base):
        raise VisionPermanentError("path_escape")
    if not target.exists() or not target.is_file():
        return None
    actual_size = target.stat().st_size
    try:
        expected_size = int(size_bytes) if size_bytes is not None else None
    except Exception:
        expected_size = None
    if expected_size is not None and int(actual_size) != int(expected_size):
        raise VisionPermanentError("size_mismatch")
    if isinstance(sha256_hex, str) and len(sha256_hex) == 64:
        import hashlib

        h = hashlib.sha256()
        with target.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        actual_hash = h.hexdigest()
        if actual_hash.lower() != sha256_hex.lower():
            raise VisionPermanentError("hash_mismatch")
    try:
        return target.read_bytes()
    except Exception:
        raise VisionPermanentError("read_error")


def _validate_loaded_submission_bytes(*, mime_type: str, data: bytes) -> None:
    try:
        validate_submission_content_signature(mime_type, data)
    except ValueError as exc:
        raise VisionPermanentError("invalid_upload_content") from exc


def _resolve_submission_image_bytes(
    *,
    submission: Dict,
    job_payload: Dict,
    bucket: str,
    max_download_bytes: int,
    meta: Dict,
) -> Optional[str]:
    """Return base64 image bytes (JPEG/PNG) from local storage or Supabase."""
    mime = (job_payload or {}).get("mime_type") or (submission or {}).get("mime_type") or ""
    mime = str(mime or "").strip().lower()
    if mime not in {JPEG_MIME, PNG_MIME}:
        return None
    root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
    storage_key = (job_payload or {}).get("storage_key") or (submission or {}).get("storage_key") or ""
    size_bytes = (job_payload or {}).get("size_bytes") or (submission or {}).get("size_bytes")
    sha256_hex = (job_payload or {}).get("sha256") or (submission or {}).get("sha256") or ""
    submission_id = (submission or {}).get("id") or ""
    if storage_key and root:
        data = _load_local_storage_bytes(
            root=root,
            storage_key=storage_key,
            size_bytes=size_bytes,
            sha256_hex=sha256_hex,
        )
        if data:
            _validate_loaded_submission_bytes(mime_type=mime, data=data)
            meta["bytes_read"] = len(data)
            return base64.b64encode(data).decode("ascii")
    if storage_key:
        srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if srk:
            obj = _strip_bucket_prefix(storage_key, bucket)
            fetched = _remote_fetch_submission_object(
                bucket=bucket,
                object_key=obj,
                srk=srk,
                max_bytes=max_download_bytes,
                submission_id=submission_id,
                success_action="fetch_remote_image",
            )
            if fetched:
                _validate_loaded_submission_bytes(mime_type=mime, data=fetched)
                meta["bytes_read"] = len(fetched)
                return base64.b64encode(fetched).decode("ascii")
    return None


class _LocalVisionAdapter:
    """DSPy-only OCR adapter used by the learning worker."""

    def __init__(self) -> None:
        self._base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
        self._api_key = (os.getenv("OPENAI_API_KEY") or "").strip() or "sk-noop"
        self._ocr_model = (os.getenv("AI_OCR_MODEL") or "").strip()
        self._ocr_think_level = (os.getenv("AI_OCR_THINK_LEVEL") or "").strip() or None
        raw_temp = (os.getenv("AI_OCR_TEMPERATURE") or "").strip()
        try:
            self._ocr_temperature = float(raw_temp) if raw_temp else 0.0
        except Exception:
            self._ocr_temperature = 0.0
        self._ocr_lm = None

    def _require_config(self) -> None:
        if not self._base_url:
            raise VisionTransientError("missing_OPENAI_BASE_URL")
        _require_secure_openai_base_url(self._base_url)
        if not self._ocr_model:
            raise VisionTransientError("missing_AI_OCR_MODEL")

    def _get_ocr_lm(self):  # type: ignore[no-untyped-def]
        if self._ocr_lm is not None:
            return self._ocr_lm
        self._require_config()
        try:
            import dspy  # type: ignore
        except Exception as exc:
            raise VisionTransientError("dspy_unavailable") from exc
        model = self._ocr_model if "/" in self._ocr_model else f"openai/{self._ocr_model}"
        lm_kwargs = {
            "temperature": self._ocr_temperature,
            "base_url": self._base_url,
            "api_key": self._api_key,
        }
        # GPT-OSS supports a per-request `think` level; keep other models unchanged.
        maybe_think = dspy_helpers.resolve_think_level(model, self._ocr_think_level)
        if maybe_think:
            lm_kwargs["extra_body"] = {"think": maybe_think}
        self._ocr_lm = dspy.LM(model, **lm_kwargs)  # type: ignore[attr-defined]
        return self._ocr_lm

    def _ensure_pdf_stitched_png(self, *, submission: Dict, job_payload: Dict) -> Optional[bytes]:
        """Return stitched PNG bytes for a PDF submission or None if unavailable.

        Why:
            Vision jobs re-run frequently; caching + logging keeps the path
            auditable and avoids expensive PDF renders when derived data already
            exists.

        Parameters:
            submission: Submission snapshot with IDs + optional page metadata.
            job_payload: Worker payload containing storage_key (fall back target).

        Behavior:
            1. Serve `derived/<submission_id>/stitched.png` when present.
            2. Stitch referenced page PNGs from `internal_metadata.page_keys`.
            3. As fallback, scan derived directories, then render from the PDF
               bytes (local or remote fetch). Persist stitched results each time.
            4. Emit structured logs (action=...) without bucket/student details.

        Permissions:
            Requires read/write access to STORAGE_VERIFY_ROOT (worker service
            account) and service-role access to Supabase Storage for remote
            fetches.
        """
        root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
        if not root:
            return None
        bucket = _submissions_bucket()
        submission_id = (submission or {}).get("id") or ""
        course_id = (submission or {}).get("course_id") or ""
        task_id = (submission or {}).get("task_id") or ""
        student_sub = (submission or {}).get("student_sub") or ""
        if not submission_id or not course_id or not task_id or not student_sub:
            return None
        from pathlib import Path
        base = Path(root).resolve()
        candidate_dirs: list["Path"] = []
        for rel in (
            f"{bucket}/{course_id}/{task_id}/{student_sub}/derived/{submission_id}",
            f"{course_id}/{task_id}/{student_sub}/derived/{submission_id}",
        ):
            try:
                cand = (base / rel).resolve()
                if os.path.commonpath([str(base), str(cand)]) != str(base):
                    continue
            except Exception:
                continue
            candidate_dirs.append(cand)
        if not candidate_dirs:
            return None
        derived_dir = candidate_dirs[0]
        stitched_path = (derived_dir / "stitched.png").resolve()

        # Return cached stitched if present (fast path for repeated jobs)
        if stitched_path.exists() and stitched_path.is_file():
            try:
                cached = stitched_path.read_bytes()
            except Exception:
                cached = None
            if cached:
                _log_storage_event(submission_id=submission_id, action="cached_stitched", size=len(cached))
                return cached
            return None

        def _persist_stitched(data: bytes) -> None:
            try:
                stitched_path.parent.mkdir(parents=True, exist_ok=True)
                stitched_path.write_bytes(data)
            except Exception:
                pass

        def _read_page_bytes(paths: list[Path]) -> list[bytes]:
            bytes_list: list[bytes] = []
            for path in paths:
                try:
                    data = path.read_bytes()
                except Exception as exc:
                    LOG.warning(
                        "learning.vision.pdf_ensure_stitched action=read_page_failed error_type=%s submission_id=%s page=%s",
                        type(exc).__name__,
                        submission_id,
                        path.name,
                    )
                    continue
                if data:
                    bytes_list.append(data)
            return bytes_list

        def _resolved_key_paths(keys: list[str]) -> list[Path]:
            resolved: list[Path] = []
            for key in keys:
                try:
                    candidate = (base / key).resolve()
                    if os.path.commonpath([str(base), str(candidate)]) != str(base):
                        continue
                except Exception:
                    continue
                resolved.append(candidate)
            return resolved

        page_keys = []
        internal_meta = (submission or {}).get("internal_metadata")
        if isinstance(internal_meta, dict):
            raw_page_keys = internal_meta.get("page_keys")
            if isinstance(raw_page_keys, list):
                page_keys = [str(k) for k in raw_page_keys if isinstance(k, str) and k.strip()]

        def _stitch_or_none(pages: list[bytes]) -> Optional[bytes]:
            if not pages:
                return None
            try:
                return stitch_images_vertically(pages)
            except Exception as exc:
                LOG.warning(
                    "learning.vision.pdf_ensure_stitched action=stitch_failed error_type=%s submission_id=%s",
                    type(exc).__name__,
                    submission_id,
                )
                return None

        if page_keys:
            resolved_paths = _resolved_key_paths(page_keys)
            page_bytes = _read_page_bytes(resolved_paths)
            stitched_png = _stitch_or_none(page_bytes)
            if stitched_png:
                _persist_stitched(stitched_png)
                _log_storage_event(
                    submission_id=submission_id,
                    action="stitch_from_page_keys",
                    pages=len(page_bytes),
                )
                return stitched_png

        # If per-page derived images exist, stitch them now
        try:
            for cand in candidate_dirs:
                if not cand.exists() or not cand.is_dir():
                    # Avoid logging derived path (may contain student identifiers)
                    LOG.warning(
                        "learning.vision.pdf_ensure_stitched action=missing_derived_dir submission_id=%s",
                        submission_id,
                    )
                    continue
                page_files = sorted(  # type: ignore[attr-defined]
                    [p for p in cand.iterdir() if p.name.startswith("page_") and p.suffix.lower() == ".png"]
                )
                if not page_files:
                    LOG.warning(
                        "learning.vision.pdf_ensure_stitched action=no_page_files submission_id=%s",
                        submission_id,
                    )
                    continue
                page_bytes = _read_page_bytes(page_files)
                stitched_png = _stitch_or_none(page_bytes)
                if stitched_png:
                    _persist_stitched(stitched_png)
                    _log_storage_event(
                        submission_id=submission_id,
                        action="stitch_from_page_dir",
                        pages=len(page_bytes),
                    )
                    return stitched_png
            # Final fallback: scan for matching derived dirs (handles legacy layouts)
            for cand in base.glob(f"**/derived/{submission_id}"):
                if not cand.is_dir():
                    continue
                page_files = sorted(  # type: ignore[attr-defined]
                    [p for p in cand.iterdir() if p.name.startswith("page_") and p.suffix.lower() == ".png"]
                )
                if not page_files:
                    continue
                page_bytes = _read_page_bytes(page_files)
                stitched_png = _stitch_or_none(page_bytes)
                if stitched_png:
                    _persist_stitched(stitched_png)
                    _log_storage_event(
                        submission_id=submission_id,
                        action="stitch_from_page_dir",
                        pages=len(page_bytes),
                    )
                    return stitched_png
        except Exception:
            pass

        # Try to read original PDF and render (local or remote fetch fallback)
        storage_key = (job_payload or {}).get("storage_key") or (submission or {}).get("storage_key") or ""
        if not storage_key:
            return None
        pdf_path = (base / storage_key).resolve()
        data: Optional[bytes] = None
        try:
            if os.path.commonpath([str(base), str(pdf_path)]) == str(base) and pdf_path.exists() and pdf_path.is_file():
                data = pdf_path.read_bytes()
                LOG.info(
                    "learning.vision.pdf_ensure_stitched action=read_local size=%s submission_id=%s",
                    len(data),
                    submission_id,
                )
        except Exception:
            data = None

        # Remote fetch from Supabase if local PDF not available
        if data is None:
            srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
            if srk and storage_key:
                obj = _strip_bucket_prefix(storage_key, bucket)
                fetched = _remote_fetch_submission_object(
                    bucket=bucket,
                    object_key=obj,
                    srk=srk,
                    max_bytes=get_learning_max_upload_bytes(),
                    submission_id=submission_id,
                    success_action="fetch_remote_pdf",
                )
                if fetched:
                    data = fetched
        if data is None:
            return None
        try:
            _validate_loaded_submission_bytes(mime_type=PDF_MIME, data=data)
            pages, _meta = process_pdf_bytes(data)
            page_bytes = [p.data for p in pages if getattr(p, "data", None)]
            stitched_png = _stitch_or_none(page_bytes)
            if not stitched_png:
                LOG.error(
                    "learning.vision.pdf_ensure_stitched action=render_no_pages submission_id=%s",
                    submission_id,
                )
                return None
            _persist_stitched(stitched_png)
            LOG.info(
                "learning.vision.pdf_ensure_stitched action=persist_derived bytes=%s submission_id=%s",
                len(stitched_png),
                submission_id,
            )
            return stitched_png
        except VisionPermanentError:
            raise
        except Exception as exc:
            try:
                err_type = type(exc).__name__
            except Exception:
                err_type = "Exception"
            LOG.error(
                "learning.vision.pdf_ensure_stitched action=render_error error_type=%s submission_id=%s",
                err_type,
                submission_id,
            )
            return None

    def extract(self, *, submission: Dict, job_payload: Dict) -> VisionResult:  # type: ignore[override]
        """Run local Vision extraction for a submission.

        Why:
            Provide a minimal, predictable Vision step in the learning worker
            pipeline that turns image/PDF submissions into Markdown text via DSPy.

        Parameters:
            submission: Minimal submission snapshot (expects keys like
                `kind`, optional `mime_type`).
            job_payload: Worker job payload holding transport details such as
                `mime_type`, `storage_key`, `size_bytes`, optional `sha256`.

        Behavior:
            - Validates MIME (except for text submissions).
            - Optionally verifies and reads a local file when
              `STORAGE_VERIFY_ROOT` and `storage_key` are provided.
            - Runs the DSPy OCR program against an OpenAI-compatible endpoint
              and returns Markdown text.
            - Classifies timeouts and empty outputs as transient (worker retries).

        Permissions:
            Runs under the learning worker's service identity; no end-user
            authorization context is required at this layer.
        """
        # Text submissions: pass-through (do not invoke external clients).
        kind = str((submission or {}).get("kind") or "").strip().lower()
        mime = str((job_payload or {}).get("mime_type") or (submission or {}).get("mime_type") or "").strip().lower()
        if kind == "text":
            # Prefer submission.text_body; allow job_payload overrides for tests.
            body = (submission or {}).get("text_body")
            if not body:
                body = (job_payload or {}).get("text_md") or (job_payload or {}).get("text_body") or ""
            text_md = str(body or "")
            meta: Dict = {"adapter": "local_vision", "backend": "pass_through", "reason": "text_submission"}
            # Strict pass-through: return as-is without any LLM normalization.
            return VisionResult(text_md=text_md, raw_metadata=meta)
        # Non-text: enforce MIME against supported types.
        if mime not in SUPPORTED_MIME:
            raise VisionPermanentError(f"unsupported mime: {mime}")

        max_download_bytes = get_learning_max_upload_bytes()
        meta: Dict = {"adapter": "local_vision", "model": self._ocr_model, "backend": "dspy"}
        image_b64: Optional[str] = None
        image_data_uri: str | None = None
        bucket = _submissions_bucket()

        # Scratch SB3: deterministic evidence extraction (no OCR).
        if mime == SCRATCH_SB3_MIME:
            from backend.storage.sb3_validation import SB3ValidationError, load_project_json
            from backend.scratch.sb3_evidence_v2 import EVIDENCE_SCHEMA_V2, build_evidence_markdown_v2

            meta = {"adapter": "local_vision", "backend": "sb3", "schema": EVIDENCE_SCHEMA_V2}
            root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
            storage_key = (job_payload or {}).get("storage_key") or (submission or {}).get("storage_key") or ""
            size_bytes = (job_payload or {}).get("size_bytes") or (submission or {}).get("size_bytes")
            sha256_hex = (job_payload or {}).get("sha256") or (submission or {}).get("sha256") or ""
            submission_id = (submission or {}).get("id") or ""
            data: bytes | None = None
            if root and storage_key:
                data = _load_local_storage_bytes(
                    root=root,
                    storage_key=storage_key,
                    size_bytes=size_bytes,
                    sha256_hex=sha256_hex,
                )
            if data is None and storage_key:
                srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
                if srk:
                    obj = _strip_bucket_prefix(str(storage_key), bucket)
                    data = _remote_fetch_submission_object(
                        bucket=bucket,
                        object_key=obj,
                        srk=srk,
                        max_bytes=max_download_bytes,
                        submission_id=str(submission_id),
                        success_action="fetch_remote_sb3",
                    )
            if not data:
                raise VisionTransientError("sb3_unavailable")
            _validate_loaded_submission_bytes(mime_type=SCRATCH_SB3_MIME, data=data)
            meta["bytes_read"] = len(data)
            try:
                project = load_project_json(data)
            except SB3ValidationError as exc:
                raise VisionPermanentError(str(exc.code))
            evidence_md = build_evidence_markdown_v2(project=project)
            if not evidence_md.strip():
                raise VisionPermanentError("empty_evidence")
            return VisionResult(text_md=evidence_md, raw_metadata=meta)

        # MakeCode HEX: deterministic evidence extraction (no OCR).
        if mime == MAKECODE_HEX_MIME:
            from backend.storage.makecode_hex_validation import MakeCodeHexValidationError, extract_makecode_project_from_hex
            from backend.makecode.hex_evidence_v1 import (
                EVIDENCE_SCHEMA_V1,
                build_evidence_markdown_v1,
                build_fallback_evidence_markdown_v1,
            )

            meta = {"adapter": "local_vision", "backend": "makecode_hex", "schema": EVIDENCE_SCHEMA_V1}
            root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
            storage_key = (job_payload or {}).get("storage_key") or (submission or {}).get("storage_key") or ""
            size_bytes = (job_payload or {}).get("size_bytes") or (submission or {}).get("size_bytes")
            sha256_hex = (job_payload or {}).get("sha256") or (submission or {}).get("sha256") or ""
            submission_id = (submission or {}).get("id") or ""
            data: bytes | None = None
            if root and storage_key:
                data = _load_local_storage_bytes(
                    root=root,
                    storage_key=storage_key,
                    size_bytes=size_bytes,
                    sha256_hex=sha256_hex,
                )
            if data is None and storage_key:
                srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
                if srk:
                    obj = _strip_bucket_prefix(str(storage_key), bucket)
                    data = _remote_fetch_submission_object(
                        bucket=bucket,
                        object_key=obj,
                        srk=srk,
                        max_bytes=max_download_bytes,
                        submission_id=str(submission_id),
                        success_action="fetch_remote_hex",
                    )
            if not data:
                raise VisionTransientError("hex_unavailable")
            _validate_loaded_submission_bytes(mime_type=MAKECODE_HEX_MIME, data=data)
            meta["bytes_read"] = len(data)
            try:
                project = extract_makecode_project_from_hex(data)
            except MakeCodeHexValidationError as exc:
                task_kind = str((job_payload or {}).get("task_kind") or "").strip().lower()
                if task_kind == "calliope" and str(exc.code) in {"invalid_hex_file", "missing_makecode_source"}:
                    meta["soft_error_code"] = str(exc.code)
                    evidence_md = build_fallback_evidence_markdown_v1(error_code=str(exc.code))
                    return VisionResult(text_md=evidence_md, raw_metadata=meta)
                raise VisionPermanentError(str(exc.code))
            evidence_md = build_evidence_markdown_v1(project=project)
            if not evidence_md.strip():
                raise VisionPermanentError("empty_evidence")
            return VisionResult(text_md=evidence_md, raw_metadata=meta)

        # Filius FLS: deterministic evidence extraction (no OCR).
        if mime == FILIUS_FLS_MIME:
            from backend.storage.filius_validation import FiliusValidationError
            from backend.filius.evidence_v1 import EVIDENCE_SCHEMA_V1, build_evidence_markdown_v1

            meta = {"adapter": "local_vision", "backend": "filius_fls", "schema": EVIDENCE_SCHEMA_V1}
            root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
            storage_key = (job_payload or {}).get("storage_key") or (submission or {}).get("storage_key") or ""
            size_bytes = (job_payload or {}).get("size_bytes") or (submission or {}).get("size_bytes")
            sha256_hex = (job_payload or {}).get("sha256") or (submission or {}).get("sha256") or ""
            submission_id = (submission or {}).get("id") or ""
            data: bytes | None = None
            if root and storage_key:
                data = _load_local_storage_bytes(
                    root=root,
                    storage_key=storage_key,
                    size_bytes=size_bytes,
                    sha256_hex=sha256_hex,
                )
            if data is None and storage_key:
                srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
                if srk:
                    obj = _strip_bucket_prefix(str(storage_key), bucket)
                    data = _remote_fetch_submission_object(
                        bucket=bucket,
                        object_key=obj,
                        srk=srk,
                        max_bytes=max_download_bytes,
                        submission_id=str(submission_id),
                        success_action="fetch_remote_fls",
                    )
            if not data:
                raise VisionTransientError("filius_unavailable")
            _validate_loaded_submission_bytes(mime_type=FILIUS_FLS_MIME, data=data)
            meta["bytes_read"] = len(data)
            try:
                evidence_md = build_evidence_markdown_v1(data)
            except FiliusValidationError as exc:
                raise VisionPermanentError(str(exc.code))
            if not evidence_md.strip():
                raise VisionPermanentError("empty_evidence")
            return VisionResult(text_md=evidence_md, raw_metadata=meta)

        if mime in {JPEG_MIME, PNG_MIME}:
            image_b64 = _resolve_submission_image_bytes(
                submission=submission,
                job_payload=job_payload,
                bucket=bucket,
                max_download_bytes=max_download_bytes,
                meta=meta,
            )
            if image_b64:
                image_data_uri = f"data:{mime};base64,{image_b64}"

        # Local fetch for PDF derived pages (independent of original PDF presence)
        if mime == PDF_MIME:
            # Validate local PDF bytes (size/hash) when a verify root is configured.
            # This must happen before derived-page stitching so tests and operators
            # get deterministic permanent errors for corrupt/mismatched uploads.
            root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
            storage_key = (job_payload or {}).get("storage_key") or (submission or {}).get("storage_key") or ""
            size_bytes = (job_payload or {}).get("size_bytes") or (submission or {}).get("size_bytes")
            sha256_hex = (job_payload or {}).get("sha256") or (submission or {}).get("sha256") or ""
            if root and storage_key:
                pdf_bytes = _load_local_storage_bytes(
                    root=root,
                    storage_key=storage_key,
                    size_bytes=size_bytes,
                    sha256_hex=sha256_hex,
                )
                if pdf_bytes:
                    _validate_loaded_submission_bytes(mime_type=PDF_MIME, data=pdf_bytes)
                    meta["bytes_read"] = len(pdf_bytes)
            stitched_png = self._ensure_pdf_stitched_png(submission=submission, job_payload=job_payload)
            if not stitched_png:
                raise VisionTransientError("pdf_images_unavailable")
            stitched_b64 = base64.b64encode(stitched_png).decode("ascii")
            image_data_uri = f"data:image/png;base64,{stitched_b64}"

        if mime in {JPEG_MIME, PNG_MIME} and not image_data_uri:
            raise VisionTransientError("image_unavailable")
        if not image_data_uri:
            raise VisionTransientError("image_unavailable")

        lm = self._get_ocr_lm()
        try:
            import dspy  # type: ignore
            from backend.learning.adapters.dspy.usage import capture_dspy_usage
            from backend.learning.adapters.dspy import vision_program

            with dspy.context(  # type: ignore[attr-defined]
                lm=lm,
                adapter=dspy.JSONAdapter(),  # type: ignore[attr-defined]
                disable_history=True,
            ):
                (text_md, program_meta), usage_events = capture_dspy_usage(
                    lambda: vision_program.extract_text_from_image(  # type: ignore[attr-defined]
                        image_data_uri=image_data_uri
                    ),
                    model=str(getattr(lm, "model", self._ocr_model) or self._ocr_model),
                    stage="ocr",
                    modality="visual",
                    call_kind="primary",
                )
        except TimeoutError as exc:
            raise VisionTransientError("timeout") from exc
        except ImportError as exc:
            raise VisionTransientError("dspy_unavailable") from exc
        except VisionTransientError:
            raise
        except VisionPermanentError:
            raise
        except Exception as exc:
            usage_events = list(getattr(exc, "usage_events", []) or [])
            raise VisionTransientError("vision_failed", usage_events=usage_events) from exc

        if not isinstance(text_md, str) or not text_md.strip():
            raise VisionTransientError("empty_ocr_text")
        if len(text_md) > 65_536:
            # Transient so the worker can retry (e.g. with a different model/backend).
            raise VisionTransientError("ocr_text_too_long")

        # Merge program meta into adapter meta for observability.
        if isinstance(program_meta, dict):
            meta.update({k: v for k, v in program_meta.items() if k not in {"text_md"}})
        return VisionResult(text_md=text_md, raw_metadata=meta, usage_events=usage_events)


def build() -> _LocalVisionAdapter:
    """Factory used by the worker DI to construct the adapter instance."""
    return _LocalVisionAdapter()
