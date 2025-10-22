"""Teaching materials service layer."""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple
from uuid import uuid4

from teaching.storage import StorageAdapterProtocol


class MaterialsRepoProtocol(Protocol):
    """Repository contract expected by the materials service."""

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool: ...

    def list_materials_for_section_owned(
        self, unit_id: str, section_id: str, author_id: str
    ) -> List[Any]: ...

    def create_markdown_material(
        self, unit_id: str, section_id: str, author_id: str, *, title: str, body_md: str
    ) -> Any: ...

    def update_material(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
        *,
        title: object = ...,
        body_md: object = ...,
        alt_text: object = ...,
    ) -> Any | None: ...

    def delete_material(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> bool: ...

    def reorder_section_materials(
        self, unit_id: str, section_id: str, author_id: str, material_ids: List[str]
    ) -> List[Any]: ...

    def get_material_owned(
        self, unit_id: str, section_id: str, material_id: str, author_id: str
    ) -> Any | None: ...

    def create_file_upload_intent(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        intent_id: str,
        material_id: str,
        storage_key: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        expires_at: datetime,
    ) -> Dict[str, Any]: ...

    def get_upload_intent_owned(
        self,
        intent_id: str,
        unit_id: str,
        section_id: str,
        author_id: str,
    ) -> Optional[Dict[str, Any]]: ...

    def finalize_upload_intent_create_material(
        self,
        intent_id: str,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        title: str,
        alt_text: Optional[str],
        sha256: str,
    ) -> Tuple[Dict[str, Any], bool]: ...


@dataclass
class MaterialFileSettings:
    """Configuration for file-based teaching materials."""

    accepted_mime_types: Tuple[str, ...] = (
        "application/pdf",
        "image/png",
        "image/jpeg",
    )
    max_size_bytes: int = 20 * 1024 * 1024
    upload_intent_ttl_seconds: int = 3 * 60
    download_url_ttl_seconds: int = 45
    storage_bucket: str = "materials"


_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_SEGMENT_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> Optional[str]:
    if not filename:
        return None
    base = os.path.basename(filename.strip())
    if not base:
        return None
    root, ext = os.path.splitext(base)
    normalized = unicodedata.normalize("NFKD", root)
    ascii_root = normalized.encode("ascii", "ignore").decode("ascii")
    sanitized_root = _SANITIZE_PATTERN.sub("-", ascii_root).strip("-_.")
    if not sanitized_root:
        sanitized_root = "file"
    sanitized_root = sanitized_root[:64]
    clean_ext = "".join(ch for ch in ext.lower() if ch.isalnum() or ch == ".")
    if clean_ext and not clean_ext.startswith("."):
        clean_ext = f".{clean_ext}"
    sanitized = f"{sanitized_root}{clean_ext}" if clean_ext else sanitized_root
    return sanitized or None


def _sanitize_segment(value: str, *, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    sanitized = _SEGMENT_SANITIZE_PATTERN.sub("-", ascii_value).strip("-_.")
    return sanitized or fallback


_UNSET = object()


@dataclass
class MaterialsService:
    """Encapsulate teaching materials use cases independent of web adapters."""

    repo: MaterialsRepoProtocol
    settings: MaterialFileSettings = field(default_factory=MaterialFileSettings)

    def ensure_section_owned(self, unit_id: str, section_id: str, author_id: str) -> None:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")

    def list_markdown_materials(self, unit_id: str, section_id: str, author_id: str) -> List[Any]:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        return self.repo.list_materials_for_section_owned(unit_id, section_id, author_id)

    def create_markdown_material(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        title: str,
        body_md: str,
    ) -> Any:
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        return self.repo.create_markdown_material(
            unit_id,
            section_id,
            author_id,
            title=title,
            body_md=body_md,
        )

    def update_material(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
        *,
        title: object = _UNSET,
        body_md: object = _UNSET,
        alt_text: object = _UNSET,
    ) -> Any:
        repo_kwargs: Dict[str, object] = {}
        if title is not _UNSET:
            repo_kwargs["title"] = title
        if body_md is not _UNSET:
            repo_kwargs["body_md"] = body_md
        if alt_text is not _UNSET:
            repo_kwargs["alt_text"] = alt_text
        result = self.repo.update_material(
            unit_id,
            section_id,
            material_id,
            author_id,
            **repo_kwargs,
        )
        if result is None:
            raise LookupError("material_not_found")
        return result

    def get_material_owned(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
    ) -> Any | None:
        return self.repo.get_material_owned(unit_id, section_id, material_id, author_id)

    def delete_material(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> None:
        deleted = self.repo.delete_material(unit_id, section_id, material_id, author_id)
        if not deleted:
            raise LookupError("material_not_found")

    def reorder_markdown_materials(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        material_ids: List[str],
    ) -> List[Any]:
        return self.repo.reorder_section_materials(unit_id, section_id, author_id, material_ids)

    def create_file_upload_intent(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        filename: str,
        mime_type: str,
        size_bytes: int,
        storage: StorageAdapterProtocol,
    ) -> Dict[str, Any]:
        if storage is None:
            raise RuntimeError("storage_adapter_not_configured")
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        sanitized = _sanitize_filename(filename)
        if not sanitized:
            raise ValueError("invalid_filename")
        normalized_mime = (mime_type or "").strip().lower()
        if normalized_mime not in self.settings.accepted_mime_types:
            raise ValueError("mime_not_allowed")
        if size_bytes <= 0 or size_bytes > self.settings.max_size_bytes:
            raise ValueError("size_exceeded")
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.settings.upload_intent_ttl_seconds)
        intent_id = str(uuid4())
        material_id = str(uuid4())
        sanitized_author = _sanitize_segment(author_id, fallback="author")
        sanitized_unit = _sanitize_segment(unit_id, fallback="unit")
        sanitized_section = _sanitize_segment(section_id, fallback="section")
        sanitized_material = _sanitize_segment(material_id, fallback="material")
        storage_key = (
            f"{self.settings.storage_bucket}/{sanitized_author}/{sanitized_unit}/{sanitized_section}/{sanitized_material}/{sanitized}"
        )
        original_name = filename.strip() or sanitized
        record = self.repo.create_file_upload_intent(
            unit_id,
            section_id,
            author_id,
            intent_id=intent_id,
            material_id=material_id,
            storage_key=storage_key,
            filename=original_name,
            mime_type=normalized_mime,
            size_bytes=size_bytes,
            expires_at=expires_at,
        )
        presign = storage.presign_upload(
            bucket=self.settings.storage_bucket,
            key=storage_key,
            expires_in=self.settings.upload_intent_ttl_seconds,
            headers={"content-type": normalized_mime},
        )
        return {
            "intent_id": record["intent_id"],
            "material_id": record["material_id"],
            "storage_key": record["storage_key"],
            "url": presign["url"],
            "headers": presign.get("headers", {}),
            "accepted_mime_types": list(self.settings.accepted_mime_types),
            "max_size_bytes": self.settings.max_size_bytes,
            "expires_at": record["expires_at"].isoformat(),
        }

    def finalize_file_material(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        intent_id: str,
        title: str,
        sha256: str,
        alt_text: Optional[str],
        storage: StorageAdapterProtocol,
    ) -> Tuple[Dict[str, Any], bool]:
        if storage is None:
            raise RuntimeError("storage_adapter_not_configured")
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        intent = self.repo.get_upload_intent_owned(intent_id, unit_id, section_id, author_id)
        if intent is None:
            raise LookupError("intent_not_found")
        now = datetime.now(timezone.utc)
        consumed_at = intent.get("consumed_at")
        if consumed_at is not None:
            material = self.repo.get_material_owned(unit_id, section_id, intent["material_id"], author_id)
            if material is None:
                raise LookupError("material_not_found")
            return material, False
        if intent["expires_at"] <= now:
            raise ValueError("intent_expired")
        normalized_title = (title or "").strip()
        if not normalized_title or len(normalized_title) > 200:
            raise ValueError("invalid_title")
        normalized_sha = (sha256 or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized_sha):
            raise ValueError("checksum_mismatch")
        head = storage.head_object(
            bucket=self.settings.storage_bucket,
            key=intent["storage_key"],
        )
        content_length = head.get("content_length")
        try:
            actual_length = int(content_length) if content_length is not None else None
        except Exception:  # pragma: no cover - defensive fallback
            actual_length = None
        if actual_length is not None and actual_length != intent["size_bytes"]:
            storage.delete_object(bucket=self.settings.storage_bucket, key=intent["storage_key"])
            raise ValueError("checksum_mismatch")
        content_type = head.get("content_type") or intent["mime_type"]
        # Accept content types with parameters (e.g., "application/pdf; charset=UTF-8").
        base_content_type = (str(content_type or "").split(";", 1)[0]).strip().lower()
        if base_content_type not in self.settings.accepted_mime_types:
            storage.delete_object(bucket=self.settings.storage_bucket, key=intent["storage_key"])
            raise ValueError("mime_not_allowed")
        if alt_text is not None and not isinstance(alt_text, str):
            raise ValueError("invalid_alt_text")
        normalized_alt = (alt_text or "").strip() or None
        if normalized_alt is not None and len(normalized_alt) > 500:
            raise ValueError("invalid_alt_text")
        material, created = self.repo.finalize_upload_intent_create_material(
            intent_id,
            unit_id,
            section_id,
            author_id,
            title=normalized_title,
            alt_text=normalized_alt,
            sha256=normalized_sha,
        )
        return material, created

    def generate_file_download_url(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
        *,
        disposition: str,
        storage: StorageAdapterProtocol,
    ) -> Dict[str, Any]:
        if storage is None:
            raise RuntimeError("storage_adapter_not_configured")
        material = self.repo.get_material_owned(unit_id, section_id, material_id, author_id)
        if material is None:
            raise LookupError("material_not_found")
        kind = material.get("kind") if isinstance(material, dict) else getattr(material, "kind", None)
        if kind != "file":
            raise LookupError("material_not_found")
        if isinstance(material, dict):
            storage_key = material.get("storage_key")
        else:
            storage_key = getattr(material, "storage_key", None)
        if not storage_key:
            raise LookupError("material_not_found")
        requested_disposition = (disposition or "attachment").strip().lower()
        if requested_disposition not in {"inline", "attachment"}:
            raise ValueError("invalid_disposition")
        presign = storage.presign_download(
            bucket=self.settings.storage_bucket,
            key=storage_key,
            expires_in=self.settings.download_url_ttl_seconds,
            disposition=requested_disposition,
        )
        url = presign["url"]
        expires_at = presign.get("expires_at")
        if not expires_at:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=self.settings.download_url_ttl_seconds)
            ).isoformat()
        return {"url": url, "expires_at": expires_at}
