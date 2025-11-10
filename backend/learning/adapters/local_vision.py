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
import os

from backend.learning.adapters.ports import (
    VisionPermanentError,
    VisionResult,
    VisionTransientError,
)
from backend.vision.pipeline import stitch_images_vertically


SUPPORTED_MIME = {"image/jpeg", "image/png", "application/pdf"}


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
                    # Infer bucket and object key; tolerate a leading bucket segment inside storage_key
                    bucket = "submissions"
                    obj = storage_key
                    if storage_key.startswith("submissions/"):
                        obj = storage_key[len("submissions/") :]
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
                    f"submissions/{course_id}/{task_id}/{student_sub}/derived/{submission_id}"
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
                    f"submissions/{course_id}/{task_id}/{student_sub}/derived/{submission_id}"
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
                            obj = page_key
                            if obj.startswith("submissions/"):
                                obj = obj[len("submissions/") :]
                            url = f"{supabase_url}/storage/v1/object/submissions/{obj}"
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
            # For PDFs with rendered pages: stitch into a single image and call once
            if mime == "application/pdf" and image_list_b64 and ("images" in params):
                try:
                    page_bytes = [base64.b64decode(b64) for b64 in image_list_b64]
                    stitched_png = stitch_images_vertically(page_bytes)
                    stitched_b64 = base64.b64encode(stitched_png).decode("ascii")
                except Exception as exc:
                    raise VisionTransientError(f"stitch_failed: {exc}")
                resp = generate(model=self._model, prompt=prompt, options=opts, images=[stitched_b64])
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
