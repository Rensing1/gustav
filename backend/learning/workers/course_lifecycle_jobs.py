"""Background jobs for private learner exports and final course deletion.

Exports are assembled in a spooled temporary file: small archives stay in
memory, while larger ones spill to disk. The worker checks the configured hard
limit before it publishes anything, so callers never receive partial archives.
"""

from __future__ import annotations

import html
import io
import json
import logging
import os
import re
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import PurePath
from typing import Any

import psycopg


LOG = logging.getLogger(__name__)
EXPORT_STORAGE_BUCKET = "learning-exports"


class ExportTooLarge(RuntimeError):
    """Raised before an oversized export is persisted."""


def build_storage_adapter_from_env():
    """Build the worker's server-side storage adapter without browser wiring."""

    base_url = str(os.getenv("SUPABASE_URL") or "").rstrip("/")
    service_key = str(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not base_url or not service_key:
        return None
    from storage3._sync.client import SyncStorageClient
    from backend.teaching.storage_supabase import SupabaseStorageAdapter

    client = SyncStorageClient(
        f"{base_url}/storage/v1",
        {"Authorization": f"Bearer {service_key}", "apikey": service_key},
    )
    return SupabaseStorageAdapter(client)


def _safe_name(value: str, fallback: str) -> str:
    name = PurePath(str(value or "").replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return name[:120] or fallback


def _html_page(snapshot: dict[str, Any], submissions: list[dict[str, Any]]) -> str:
    course = snapshot.get("course") if isinstance(snapshot.get("course"), dict) else {}
    entries: list[str] = []
    for item in submissions:
        task = item.get("task_snapshot") if isinstance(item.get("task_snapshot"), dict) else {}
        title = str(task.get("title") or task.get("instruction_md") or "Aufgabe")
        parts = [f"<article><h2>{html.escape(title)}</h2>"]
        if item.get("text_body"):
            parts.append(f"<h3>Meine Abgabe</h3><p>{html.escape(str(item['text_body']))}</p>")
        if item.get("export_file"):
            href = html.escape(str(item["export_file"]), quote=True)
            parts.append(f'<p><a href="{href}">Originaldatei öffnen</a></p>')
        if item.get("feedback_md"):
            parts.append(f"<h3>Rückmeldung</h3><p>{html.escape(str(item['feedback_md']))}</p>")
        parts.append("</article>")
        entries.append("".join(parts))
    return """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Lernarchiv</title>
<style>body{font:16px/1.6 system-ui,sans-serif;max-width:70ch;margin:2rem auto;padding:0 1rem;color:#181818}article{padding:1.5rem 0;border-bottom:1px solid #777}h1,h2,h3{line-height:1.2}a{color:#8c1a00}</style>
</head><body><h1>""" + html.escape(str(course.get("title") or "Lernarchiv")) + "</h1>" + "".join(entries) + "</body></html>"


def build_export_zip(
    snapshot: dict[str, Any],
    *,
    load_file: Callable[[str], bytes],
    max_bytes: int,
) -> bytes:
    """Build a complete safe archive and enforce the hard limit pre-publish."""

    raw_submissions = snapshot.get("submissions")
    submissions = [dict(item) for item in raw_submissions if isinstance(item, dict)] if isinstance(raw_submissions, list) else []
    manifest_submissions: list[dict[str, Any]] = []
    files: list[tuple[str, bytes]] = []
    used_names: set[str] = set()
    total_input = 0
    for index, item in enumerate(submissions, start=1):
        storage_key = str(item.pop("storage_key", "") or "")
        if storage_key:
            payload = load_file(storage_key)
            total_input += len(payload)
            if total_input > max_bytes:
                raise ExportTooLarge("export_too_large")
            base = _safe_name(storage_key, f"datei-{index}.bin")
            name = f"dateien/{index:03d}-{base}"
            while name in used_names:
                name = f"dateien/{index:03d}-{len(used_names)}-{base}"
            used_names.add(name)
            item["export_file"] = name
            files.append((name, payload))
        manifest_submissions.append(item)

    manifest = {
        "version": 1,
        "created_from_cutoff": snapshot.get("cutoff_at"),
        "course": snapshot.get("course") if isinstance(snapshot.get("course"), dict) else {},
        "submissions": manifest_submissions,
    }
    with tempfile.SpooledTemporaryFile(max_size=min(max_bytes, 8 * 1024 * 1024)) as spool:
        with zipfile.ZipFile(spool, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("index.html", _html_page(snapshot, manifest_submissions).encode("utf-8"))
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
            for name, payload in files:
                archive.writestr(name, payload)
        size = spool.tell()
        if size > max_bytes:
            raise ExportTooLarge("export_too_large")
        spool.seek(0)
        return spool.read()


def _download(adapter, *, bucket: str, key: str, max_bytes: int) -> bytes:
    import requests

    signed = adapter.presign_download(bucket=bucket, key=key, expires_in=120, disposition="attachment")
    response = requests.get(str(signed["url"]), headers=dict(signed.get("headers") or {}), stream=True, timeout=30)
    response.raise_for_status()
    body = io.BytesIO()
    for chunk in response.iter_content(64 * 1024):
        body.write(chunk)
        if body.tell() > max_bytes:
            raise ExportTooLarge("export_too_large")
    return body.getvalue()


def process_export_once(*, dsn: str, storage_adapter, max_bytes: int | None = None) -> bool:
    """Claim and publish one export under the dedicated worker role."""

    limit = max_bytes or int(os.getenv("LEARNING_EXPORT_MAX_BYTES", str(1024 * 1024 * 1024)))
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select (public.learning_worker_claim_export()).id::text")
            row = cur.fetchone()
            conn.commit()
        if not row or not row[0]:
            return False
        job_id = str(row[0])
        try:
            with conn.cursor() as cur:
                cur.execute("select public.learning_worker_export_snapshot(%s::uuid)", (job_id,))
                snapshot_row = cur.fetchone()
            snapshot = snapshot_row[0] if snapshot_row and isinstance(snapshot_row[0], dict) else {}
            archive = build_export_zip(
                snapshot,
                load_file=lambda key: _download(storage_adapter, bucket="submissions", key=key, max_bytes=limit),
                max_bytes=limit,
            )
            storage_key = f"exports/{job_id}.zip"
            storage_adapter.put_object(
                bucket=EXPORT_STORAGE_BUCKET,
                key=storage_key,
                body=archive,
                content_type="application/zip",
            )
            with conn.cursor() as cur:
                cur.execute("select public.learning_worker_complete_export(%s::uuid, %s, %s)", (job_id, storage_key, len(archive)))
            conn.commit()
        except Exception as exc:
            code = "export_too_large" if isinstance(exc, ExportTooLarge) else "export_failed"
            # Keep operational logs content-free while retaining the exception
            # class needed to diagnose storage and archive failures.
            LOG.warning("learning.export.failed error_code=%s error_type=%s", code, type(exc).__name__)
            with conn.cursor() as cur:
                cur.execute("select public.learning_worker_fail_export(%s::uuid, %s)", (job_id, code))
            conn.commit()
        return True


def process_deletion_once(*, dsn: str, storage_adapter) -> bool:
    """Delete one queued object, then finalize an empty deletion outbox."""

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """update public.course_deletion_jobs set status='processing', started_at=coalesce(started_at, now())
                   where id=(select id from public.course_deletion_jobs where status in ('pending','processing') order by created_at for update skip locked limit 1)
                   returning id::text"""
            )
            job = cur.fetchone()
            conn.commit()
        if not job:
            return False
        job_id = str(job[0])
        with conn.cursor() as cur:
            cur.execute(
                "select id::text, bucket, storage_key from public.storage_deletion_outbox where deletion_job_id=%s::uuid and status<>'deleted' order by created_at limit 1",
                (job_id,),
            )
            item = cur.fetchone()
        if item:
            try:
                storage_adapter.delete_object(bucket=item[1], key=item[2])
                with conn.cursor() as cur:
                    cur.execute("update public.storage_deletion_outbox set status='deleted', updated_at=now(), last_error_code=null where id=%s::uuid", (item[0],))
            except Exception:
                with conn.cursor() as cur:
                    cur.execute("update public.storage_deletion_outbox set status='failed', retry_count=least(retry_count+1,20), updated_at=now(), last_error_code='storage_delete_failed' where id=%s::uuid", (item[0],))
            conn.commit()
            return True
        with conn.cursor() as cur:
            cur.execute("select public.finalize_course_deletion(%s::uuid)", (job_id,))
        conn.commit()
        return True


def process_expired_export_once(*, dsn: str, storage_adapter) -> bool:
    """Remove one expired private ZIP and retain only inhaltsfreie job metadata."""

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """select id::text, storage_key from public.learning_export_jobs
                    where expires_at <= now() and status <> 'expired'
                    order by expires_at for update skip locked limit 1"""
            )
            row = cur.fetchone()
            if not row:
                return False
            if row[1]:
                try:
                    storage_adapter.delete_object(bucket=EXPORT_STORAGE_BUCKET, key=row[1])
                except Exception:
                    conn.rollback()
                    return True
            cur.execute(
                "update public.learning_export_jobs set status='expired', storage_key=null, size_bytes=null where id=%s::uuid",
                (row[0],),
            )
            conn.commit()
    return True
