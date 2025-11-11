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
from typing import Dict, Optional
import base64
import inspect
import logging

from backend.learning.adapters.ports import (
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)
from backend.vision.pipeline import stitch_images_vertically, process_pdf_bytes
from backend.storage.config import get_submissions_bucket

LOG = logging.getLogger(__name__)


SUPPORTED_MIME = {"image/jpeg", "image/png", "application/pdf"}


def _submissions_bucket() -> str:
    return get_submissions_bucket()


def _strip_bucket_prefix(key: str, bucket: str) -> str:
    prefix = f"{bucket}/"
    if key.startswith(prefix):
        return key[len(prefix) :]
    return key


class _LocalVisionAdapter:
    """Minimal Vision adapter backed by a local Ollama client.

    The adapter does not access storage in this minimal version; it simply
    demonstrates the call-out shape and error mapping required by tests.
    """

    def __init__(self) -> None:
        self._model = os.getenv("AI_VISION_MODEL", os.getenv("OLLAMA_VISION_MODEL", "llama3.2-vision"))
        self._base_url = os.getenv("OLLAMA_BASE_URL")
        # Keep a small, safe timeout budget. Tests don't depend on this.
        self._timeout = int(os.getenv("AI_TIMEOUT_VISION", "30"))

    def _ensure_pdf_stitched_png(self, *, submission: Dict, job_payload: Dict) -> Optional[bytes]:
        """Return stitched PNG bytes for a PDF submission or None if unavailable.

        Strategy (KISS):
        - Prefer a precomputed derived image at derived/<submission_id>/stitched.png under STORAGE_VERIFY_ROOT.
        - Look for existing derived page keys stored in `internal_metadata.page_keys` before re-rendering.
        - Otherwise, read the original PDF from STORAGE_VERIFY_ROOT or Supabase and render pages via process_pdf_bytes,
          stitch them vertically, and persist stitched.png for reuse.
        - If none of these paths succeed, return None so the caller can retry later.
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

        # Return cached stitched if present
        if stitched_path.exists() and stitched_path.is_file():
            try:
                return stitched_path.read_bytes()
            except Exception:
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
            supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
            srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
            if supabase_url and srk and storage_key:
                obj = _strip_bucket_prefix(storage_key, bucket)
                url = f"{supabase_url}/storage/v1/object/{bucket}/{obj}"
                try:
                    import httpx  # type: ignore

                    resp = httpx.get(
                        url,
                        headers={
                            "apikey": srk,
                            "Authorization": f"Bearer {srk}",
                        },
                        timeout=15,
                    )
                    if 200 <= int(getattr(resp, "status_code", 0)) < 300:
                        content = bytes(getattr(resp, "content", b""))
                        ctype = str(getattr(resp, "headers", {}).get("content-type", ""))
                        if content:
                            if (not ctype.lower().startswith("application/pdf")) and (not content.startswith(b"%PDF-")):
                                LOG.warning(
                                    "learning.vision.pdf_ensure_stitched action=wrong_content status=%s ctype=%s size=%s submission_id=%s",
                                    getattr(resp, "status_code", ""),
                                    ctype,
                                    len(content),
                                    submission_id,
                                )
                            else:
                                data = content
                                LOG.info(
                                    "learning.vision.pdf_ensure_stitched action=fetch_remote size=%s submission_id=%s",
                                    len(content),
                                    submission_id,
                                )
                except Exception:
                    pass
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

            if storage_key and root:
                try:
                    from pathlib import Path
                    base = Path(root).resolve()
                    target = (base / storage_key).resolve()
                    common = os.path.commonpath([str(base), str(target)])
                except Exception:
                    raise VisionPermanentError("path_error")
                if common != str(base):
                    raise VisionPermanentError("path_escape")
                # If the file is not present locally, do not classify as permanent yet.
                # We will attempt a remote fetch and, if that also fails, treat as transient
                # so the worker can retry when storage latency resolves.
                if not target.exists() or not target.is_file():
                    target = None  # type: ignore[assignment]
                else:
                    actual_size = target.stat().st_size
                    try:
                        expected_size = int(size_bytes) if size_bytes is not None else None
                    except Exception:
                        expected_size = None
                    if expected_size is not None and int(actual_size) != int(expected_size):
                        raise VisionPermanentError("size_mismatch")
                    # Compute sha256 if provided
                    if isinstance(sha256_hex, str) and len(sha256_hex) == 64:
                        import hashlib
                        h = hashlib.sha256()
                        with target.open("rb") as fh:  # type: ignore[union-attr]
                            for chunk in iter(lambda: fh.read(65536), b""):
                                h.update(chunk)
                        actual_hash = h.hexdigest()
                        if actual_hash.lower() != sha256_hex.lower():
                            raise VisionPermanentError("hash_mismatch")
                    # Read bytes (for potential OCR libs) — here only for observability
                    try:
                        data = target.read_bytes()  # type: ignore[union-attr]
                        meta["bytes_read"] = len(data)
                        if mime in {"image/jpeg", "image/png"}:
                            image_b64 = base64.b64encode(data).decode("ascii")
                        # For PDFs, fetching derived page images is handled below as well
                    except Exception:
                        raise VisionPermanentError("read_error")

            # Fallback: if local root not provided or file not found, try Supabase fetch
            if (not image_b64) and storage_key and mime in {"image/jpeg", "image/png"}:
                supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
                srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
                if supabase_url and srk:
                    # Infer object key; tolerate a leading bucket segment inside storage_key
                    obj = _strip_bucket_prefix(storage_key, bucket)
                    url = f"{supabase_url}/storage/v1/object/{bucket}/{obj}"
                    try:
                        import httpx  # type: ignore

                        resp = httpx.get(
                            url,
                            headers={
                                "apikey": srk,
                                "Authorization": f"Bearer {srk}",
                            },
                            timeout=10,
                        )
                        if int(getattr(resp, "status_code", 0)) >= 200 and int(getattr(resp, "status_code", 0)) < 300:
                            data = bytes(getattr(resp, "content", b""))
                            if data:
                                image_b64 = base64.b64encode(data).decode("ascii")
                                meta["bytes_read"] = len(data)
                    except Exception:
                        # Remote fetch failures are treated as non-fatal: continue without images
                        pass

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
                supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
                srk = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
                if derived_prefix and supabase_url and srk:
                    try:
                        import httpx  # type: ignore
                    except Exception:
                        httpx = None  # type: ignore
                    if httpx is not None:
                        for idx in range(1, 6):
                            page_key = f"{derived_prefix}/page_{idx:04}.png"
                            obj = _strip_bucket_prefix(page_key, bucket)
                            url = f"{supabase_url}/storage/v1/object/{bucket}/{obj}"
                            try:
                                resp = httpx.get(
                                    url,
                                    headers={
                                        "apikey": srk,
                                        "Authorization": f"Bearer {srk}",
                                    },
                                    timeout=10,
                                )
                                if 200 <= int(getattr(resp, "status_code", 0)) < 300:
                                    data = bytes(getattr(resp, "content", b""))
                                    if data:
                                        image_list_b64.append(base64.b64encode(data).decode("ascii"))
                            except Exception:
                                continue

            # At this point, for image/jpeg|png we require bytes to avoid model
            # calls without visual inputs. If still missing, classify as transient
            # so the worker can retry when storage becomes available.
            if mime in {"image/jpeg", "image/png"} and not image_b64:
                raise VisionTransientError("image_unavailable")

        # Intentionally prefer Ollama for Vision even when DSPy is importable.
        # Rationale: E2E contract expects Vision to be backed by the local
        # Ollama service while DSPy is reserved for Feedback analysis. This
        # keeps responsibilities clear and makes behaviour predictable in dev/CI.

        # Import client lazily so tests can monkeypatch sys.modules["ollama"].
        try:
            import ollama  # type: ignore
        except Exception as exc:  # pragma: no cover - defensive, tests install a fake client
            raise VisionTransientError(f"ollama client unavailable: {exc}")

        prompt = (
            "Transcribe the exact visible text as Markdown.\n"
            "- Verbatim OCR: do not summarize or invent structure.\n"
            "- No placeholders, no fabrications, no disclaimers.\n"
            "- Preserve line breaks; omit decorative headers/footers.\n\n"
            f"Input kind: {kind or 'unknown'}; mime: {mime or 'n/a'}.\n"
            "If the content is an image or a scanned PDF page, return only the text you can read."
        )
        try:
            # Construct client with positional host argument for compatibility
            # with real clients that expect `host` rather than `base_url`.
            client = ollama.Client(self._base_url)
            # Options include a timeout; use low temperature to reduce hallucinations.
            opts = {"timeout": self._timeout, "temperature": 0}
            # Pass images when supported by the client and available
            generate = getattr(client, "generate")
            params = set(inspect.signature(generate).parameters.keys())
            # For PDFs: strictly require a single stitched image; never call without images.
            # Do not rely on the client's signature exposing an explicit `images` parameter;
            # some clients accept **kwargs. We always pass `images=[...]` for PDFs.
            if mime == "application/pdf":
                stitched_png = self._ensure_pdf_stitched_png(submission=submission, job_payload=job_payload)
                if not stitched_png:
                    raise VisionTransientError("pdf_images_unavailable")
                try:
                    stitched_b64 = base64.b64encode(stitched_png).decode("ascii")
                    resp = generate(model=self._model, prompt=prompt, options=opts, images=[stitched_b64])
                except TimeoutError as exc:
                    raise VisionTransientError(str(exc))
                except Exception as exc:
                    raise VisionTransientError(str(exc))
                text = ""
                if isinstance(resp, dict):
                    text = str(resp.get("response", "")).strip()
                if text.startswith("```") and text.endswith("```"):
                    lines_i = text.splitlines()
                    if len(lines_i) >= 3 and lines_i[-1].strip() == "```":
                        text = "\n".join(lines_i[1:-1]).strip()
                return VisionResult(text_md=text or "", raw_metadata=meta)
            # Single image (JPEG/PNG)
            if image_b64 and ("images" in params):
                response = generate(model=self._model, prompt=prompt, options=opts, images=[image_b64])
            else:
                response = generate(model=self._model, prompt=prompt, options=opts)
        except TimeoutError as exc:
            raise VisionTransientError(str(exc))
        except Exception as exc:  # pragma: no cover - conservative mapping
            # Treat generic client errors as transient in this minimal adapter.
            raise VisionTransientError(str(exc))

        text = ""  # default safe fallback
        if isinstance(response, dict):
            text = str(response.get("response", "")).strip()
        # Unwrap accidental fenced code blocks (```markdown ... ``` or ``` ... ```)
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1]).strip()
        if not text:
            # Empty outputs are considered transient so the worker can retry.
            raise VisionTransientError("empty response from local vision")

        return VisionResult(text_md=text, raw_metadata=meta)


def build() -> _LocalVisionAdapter:
    """Factory used by the worker DI to construct the adapter instance."""
    return _LocalVisionAdapter()

    
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
