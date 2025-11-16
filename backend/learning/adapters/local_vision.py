"""
Local Vision adapter using a simple Ollama client call.

Intent:
    Provide the minimal implementation required by the adapter TDD tests:
      - Support JPEG/PNG/PDF via job_payload["mime_type"].
      - Return a VisionResult with Markdown text and simple metadata.
      - Classify client timeouts as VisionTransientError.
      - Classify unsupported MIME types as VisionPermanentError.

Notes:
    - We import the error/result types from the worker module to keep contracts
      aligned with existing tests and ports.
    - We import `ollama` lazily inside the method so test monkeypatching works.
"""

from __future__ import annotations

import os
import ipaddress
from typing import Dict, Optional
import base64
import inspect
import logging
from urllib.parse import urlparse as _urlparse

from backend.learning.adapters.ports import (
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)
from backend.vision.pipeline import stitch_images_vertically, process_pdf_bytes
from backend.storage.config import get_submissions_bucket, get_learning_max_upload_bytes

LOG = logging.getLogger(__name__)


SUPPORTED_MIME = {"image/jpeg", "image/png", "application/pdf"}
_LOCAL_HTTP_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}


def _is_local_host(host: str) -> bool:
    """Return True if host resolves to loopback/private or uses .local suffix."""
    if host in _LOCAL_HTTP_HOSTS or host.endswith(".local"):
        return True
    try:
        parsed = ipaddress.ip_address(host)
        return bool(parsed.is_loopback or parsed.is_private)
    except ValueError:
        return False


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
    if mime not in {"image/jpeg", "image/png"}:
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
                meta["bytes_read"] = len(fetched)
                return base64.b64encode(fetched).decode("ascii")
    return None


def _call_model(
    *,
    mime: str,
    prompt: str,
    model: str,
    base_url: str,
    timeout: int,
    image_b64: str | None,
    image_list_b64: list[str] | None,
) -> str:
    """Invoke the Ollama vision model with optional image inputs."""
    try:
        import ollama  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        raise VisionTransientError(f"ollama client unavailable: {exc}")

    images_payload: list[str] | None = None
    if mime == "application/pdf" and image_list_b64:
        images_payload = image_list_b64
    elif image_b64:
        images_payload = [image_b64]
    elif image_list_b64:
        images_payload = image_list_b64

    try:
        client = ollama.Client(base_url)
        opts = {"timeout": timeout, "temperature": 0}
        generate = getattr(client, "generate")
        signature = inspect.signature(generate)
        params = set(signature.parameters.keys())
        accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())
        kwargs: Dict[str, object] = {"model": model, "prompt": prompt, "options": opts}
        if images_payload and (mime == "application/pdf" or "images" in params or accepts_kwargs):
            kwargs["images"] = images_payload
        response = generate(**kwargs)
    except TimeoutError as exc:
        raise VisionTransientError(str(exc))
    except Exception as exc:  # pragma: no cover - conservative mapping
        raise VisionTransientError(str(exc))

    text = ""
    if isinstance(response, dict):
        text = str(response.get("response", "")).strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    return text


class _LocalVisionAdapter:
    """Minimal Vision adapter backed by a local Ollama client.

    The adapter does not access storage in this minimal version; it simply
    demonstrates the call-out shape and error mapping required by tests.
    """

    def __init__(self) -> None:
        self._model = os.getenv("AI_VISION_MODEL", os.getenv("OLLAMA_VISION_MODEL", "llama3.2-vision"))
        raw_base_url = os.getenv("OLLAMA_BASE_URL")
        # Mirror the feedback adapter behaviour: prefer explicit base URL and
        # fall back to the docker-compose default host when unset.
        self._base_url = (raw_base_url or "").strip() or "http://ollama:11434"
        # Keep a small, safe timeout budget. Tests don't depend on this.
        self._timeout = int(os.getenv("AI_TIMEOUT_VISION", "30"))

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
                except Exception:
                    LOG.warning(
                        "learning.vision.pdf_ensure_stitched action=read_page_failed submission_id=%s path=%s",
                        submission_id,
                        path,
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
                    "learning.vision.pdf_ensure_stitched action=stitch_failed error_type=%s message=%s submission_id=%s",
                    type(exc).__name__,
                    str(exc)[:120],
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
                try:
                    fetched = _remote_fetch_submission_object(
                        bucket=bucket,
                        object_key=obj,
                        srk=srk,
                        max_bytes=get_learning_max_upload_bytes(),
                        submission_id=submission_id,
                        success_action="fetch_remote_pdf",
                    )
                except VisionTransientError as exc:
                    reason = str(exc)
                    if reason in {"untrusted_host", "remote_fetch_failed"}:
                        fetched = None
                    else:
                        raise
                if fetched:
                    data = fetched
        if data is None:
            return None
        try:
            if not data.startswith(b"%PDF-"):
                LOG.warning(
                    "learning.vision.pdf_ensure_stitched action=wrong_content_pre_render size=%s submission_id=%s",
                    len(data),
                    submission_id,
                )
                return None
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
        except Exception as exc:
            try:
                err_type = type(exc).__name__
                err_msg = str(exc)
            except Exception:
                err_type = "Exception"
                err_msg = "(unavailable)"
            LOG.error(
                "learning.vision.pdf_ensure_stitched action=render_error error_type=%s message=%s submission_id=%s",
                err_type,
                err_msg[:120],
                submission_id,
            )
            return None

    def extract(self, *, submission: Dict, job_payload: Dict) -> VisionResult:  # type: ignore[override]
        """Run local Vision extraction for a submission.

        Why:
            Provide a minimal, predictable Vision step in the learning worker
            pipeline that extracts/summarizes textual content via a local
            Ollama runtime. Kept intentionally simple for didactic purposes.

        Parameters:
            submission: Minimal submission snapshot (expects keys like
                `kind`, optional `mime_type`).
            job_payload: Worker job payload holding transport details such as
                `mime_type`, `storage_key`, `size_bytes`, optional `sha256`.

        Behavior:
            - Validates MIME (except for text submissions).
            - Optionally verifies and reads a local file when
              `STORAGE_VERIFY_ROOT` and `storage_key` are provided.
            - Calls the local Ollama client and returns Markdown text.
            - Classifies timeouts and empty outputs as transient.

        Permissions:
            Runs under the learning worker's service identity; no end-user
            authorization context is required at this layer.
        """
        # Text submissions: pass-through (do not invoke external clients).
        kind = (submission or {}).get("kind") or ""
        mime = (job_payload or {}).get("mime_type") or (submission or {}).get("mime_type") or ""
        if kind == "text":
            # Prefer submission.text_body; allow job_payload overrides for tests.
            body = (submission or {}).get("text_body")
            if not body:
                body = (job_payload or {}).get("text_md") or (job_payload or {}).get("text_body") or ""
            text_md = str(body or "").strip() or "# (empty submission)"
            meta: Dict = {"adapter": "local_vision", "model": self._model, "backend": "pass_through"}
            # Strict pass-through: return as-is without any LLM normalization.
            return VisionResult(text_md=text_md, raw_metadata=meta)
        # Non-text: enforce MIME against supported types.
        if mime not in SUPPORTED_MIME:
            raise VisionPermanentError(f"unsupported mime: {mime}")

        max_download_bytes = get_learning_max_upload_bytes()
        # Stream bytes from local storage when configured for non-text kinds.
        # We intentionally avoid importing the web layer; implement a minimal
        # verification here mirroring the path guard and integrity checks.
        meta: Dict = {"adapter": "local", "model": self._model, "backend": "ollama"}
        image_b64: Optional[str] = None
        # For PDFs we can pass multiple page images; collect them here when available
        image_list_b64: list[str] = []
        bucket = _submissions_bucket()
        if kind != "text":
            root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip()
            # Fallback to submission fields when job payload omits transport metadata.
            storage_key = (job_payload or {}).get("storage_key") or (submission or {}).get("storage_key") or ""
            size_bytes = (job_payload or {}).get("size_bytes") or (submission or {}).get("size_bytes")
            sha256_hex = (job_payload or {}).get("sha256") or (submission or {}).get("sha256") or ""
            # Submission identity (used to infer derived page keys for PDFs)
            submission_id = (submission or {}).get("id") or ""
            course_id = (submission or {}).get("course_id") or ""
            task_id = (submission or {}).get("task_id") or ""
            student_sub = (submission or {}).get("student_sub") or ""

            if mime in {"image/jpeg", "image/png"}:
                image_b64 = _resolve_submission_image_bytes(
                    submission=submission,
                    job_payload=job_payload,
                    bucket=bucket,
                    max_download_bytes=max_download_bytes,
                    meta=meta,
                )

            if mime == "application/pdf" and storage_key and root:
                data = _load_local_storage_bytes(
                    root=root,
                    storage_key=storage_key,
                    size_bytes=size_bytes,
                    sha256_hex=sha256_hex,
                )
                if data:
                    meta["bytes_read"] = len(data)

            # Local fetch for PDF derived pages (independent of original PDF presence)
            if mime == "application/pdf" and root and not image_list_b64:
                from pathlib import Path as _P
                base = _P(root).resolve()
                derived_prefix = (
                    f"{bucket}/{course_id}/{task_id}/{student_sub}/derived/{submission_id}"
                    if course_id and task_id and student_sub and submission_id
                    else None
                )
                if derived_prefix:
                    for idx in range(1, 6):
                        page_path = (base / f"{derived_prefix}/page_{idx:04}.png").resolve()
                        try:
                            common2 = os.path.commonpath([str(base), str(page_path)])
                        except Exception:
                            continue
                        if common2 != str(base):
                            continue
                        if page_path.exists() and page_path.is_file():
                            try:
                                pb = page_path.read_bytes()
                                image_list_b64.append(base64.b64encode(pb).decode("ascii"))
                            except Exception:
                                continue

            # Remote fetch for PDF derived pages (if local read failed)
            if mime == "application/pdf" and not image_list_b64:
                derived_prefix = (
                    f"{bucket}/{course_id}/{task_id}/{student_sub}/derived/{submission_id}"
                    if course_id and task_id and student_sub and submission_id
                    else None
                )
                srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
                if derived_prefix and srk:
                    for idx in range(1, 6):
                        page_key = f"{derived_prefix}/page_{idx:04}.png"
                        obj = _strip_bucket_prefix(page_key, bucket)
                        data, reason = _download_supabase_object(
                            bucket=bucket,
                            object_key=obj,
                            srk=srk,
                            max_bytes=max_download_bytes,
                        )
                        if reason == "size_exceeded":
                            raise VisionTransientError("remote_fetch_too_large")
                        if reason == "untrusted_host":
                            _log_storage_event(
                                submission_id=submission_id,
                                action="remote_fetch_failed",
                                reason=reason,
                                stage="pdf_page",
                            )
                            continue
                        if reason and reason != "ok":
                            if reason.startswith("http_error:400"):
                                _log_storage_event(
                                    submission_id=submission_id,
                                    action="remote_fetch_failed",
                                    reason=reason,
                                    stage="pdf_page",
                                )
                                continue
                            _log_storage_event(
                                submission_id=submission_id,
                                action="remote_fetch_failed",
                                reason=reason,
                                stage="pdf_page",
                            )
                            raise VisionTransientError("remote_fetch_failed")
                        if data:
                            image_list_b64.append(base64.b64encode(data).decode("ascii"))

            # At this point, for image/jpeg|png we require bytes to avoid model
            # calls without visual inputs. If still missing, classify as transient
            # so the worker can retry when storage becomes available.
            if mime in {"image/jpeg", "image/png"} and not image_b64:
                raise VisionTransientError("image_unavailable")

        prompt = (
            "Transcribe the exact visible text as Markdown.\n"
            "- Verbatim OCR: do not summarize or invent structure.\n"
            "- No placeholders, no fabrications, no disclaimers.\n"
            "- Preserve line breaks; omit decorative headers/footers.\n\n"
            f"Input kind: {kind or 'unknown'}; mime: {mime or 'n/a'}.\n"
            "If the content is an image or a scanned PDF page, return only the text you can read."
        )
        if mime == "application/pdf":
            stitched_png = self._ensure_pdf_stitched_png(submission=submission, job_payload=job_payload)
            if not stitched_png:
                raise VisionTransientError("pdf_images_unavailable")
            stitched_b64 = base64.b64encode(stitched_png).decode("ascii")
            text = _call_model(
                mime=mime,
                prompt=prompt,
                model=self._model,
                base_url=self._base_url,
                timeout=self._timeout,
                image_b64=None,
                image_list_b64=[stitched_b64],
            )
            if not text:
                raise VisionTransientError("empty response from local vision")
            return VisionResult(text_md=text, raw_metadata=meta)

        text = _call_model(
            mime=mime,
            prompt=prompt,
            model=self._model,
            base_url=self._base_url,
            timeout=self._timeout,
            image_b64=image_b64,
            image_list_b64=image_list_b64,
        )
        if not text:
            # Empty outputs are considered transient so the worker can retry.
            raise VisionTransientError("empty response from local vision")

        return VisionResult(text_md=text, raw_metadata=meta)


def build() -> _LocalVisionAdapter:
    """Factory used by the worker DI to construct the adapter instance."""
    return _LocalVisionAdapter()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
