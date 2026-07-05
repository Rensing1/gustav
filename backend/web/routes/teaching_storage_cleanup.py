"""Storage cleanup helpers for Teaching unit deletion.

Why:
    Deleting a learning unit can cascade database rows, but object storage does
    not participate in PostgreSQL foreign keys. These helpers collect and delete
    affected storage objects before the database delete so failures can abort
    without leaving rows that point at already-deleted files.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.storage.config import get_submissions_bucket

LOG = logging.getLogger("gustav.web.teaching")


def unit_delete_storage_metadata_dsn(repo: object) -> str | None:
    """Return the DSN used to read storage keys before a unit delete."""

    return (
        str(getattr(repo, "_service_dsn", "") or "").strip()
        or str(getattr(repo, "_dsn", "") or "").strip()
        or None
    )


def metadata_page_keys(internal_metadata: Any) -> list[str]:
    """Extract PDF-derived page keys from a learning submission metadata value."""

    metadata = internal_metadata
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return []
    if not isinstance(metadata, dict):
        return []
    raw_page_keys = metadata.get("page_keys")
    if not isinstance(raw_page_keys, list):
        return []
    return [str(key).strip() for key in raw_page_keys if str(key or "").strip()]


def collect_unit_delete_storage_objects(
    repo: object,
    *,
    unit_id: str,
    materials_bucket: str,
) -> list[tuple[str, str]]:
    """Collect object storage entries that must be removed before deleting a unit.

    Permissions:
        The caller must already have passed the author guard for this unit.
    """

    dsn = unit_delete_storage_metadata_dsn(repo)
    if not dsn:
        return []
    from backend.web.db_cursor import open_repo_cursor

    objects: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(bucket: str, key: str | None) -> None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return
        item = (bucket, normalized_key)
        if item not in seen:
            seen.add(item)
            objects.append(item)

    try:
        with open_repo_cursor(dsn=dsn) as (_conn, cur):
            cur.execute(
                """
                select storage_key
                  from public.unit_materials
                 where unit_id = %s
                   and kind = 'file'
                   and storage_key is not null
                """,
                (unit_id,),
            )
            for row in cur.fetchall():
                add(materials_bucket, row[0])

            cur.execute(
                """
                select ls.storage_key, ls.internal_metadata
                  from public.learning_submissions ls
                  join public.unit_tasks t on t.id = ls.task_id
                 where t.unit_id = %s
                   and (ls.storage_key is not null or ls.internal_metadata ? 'page_keys')
                """,
                (unit_id,),
            )
            submissions_bucket = get_submissions_bucket()
            for storage_key, internal_metadata in cur.fetchall():
                add(submissions_bucket, storage_key)
                for page_key in metadata_page_keys(internal_metadata):
                    add(submissions_bucket, page_key)
    except Exception:
        LOG.warning("unit delete storage metadata unavailable unit_id=%s", unit_id, exc_info=True)
        raise RuntimeError("storage_metadata_unavailable")

    return objects


def delete_storage_objects(storage_adapter: object, objects: list[tuple[str, str]]) -> None:
    """Delete collected storage objects, failing closed when storage is unavailable."""

    if not objects:
        return
    delete_object = getattr(storage_adapter, "delete_object", None)
    if not callable(delete_object):
        raise RuntimeError("storage_adapter_not_configured")
    for bucket, key in objects:
        delete_object(bucket=bucket, key=key)
