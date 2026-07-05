"""Storage adapter interface for teaching materials."""
from __future__ import annotations

from typing import Any, Dict, Protocol


class StorageAdapterProtocol(Protocol):
    """Protocol describing the storage adapter used for file materials."""

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: Dict[str, str]) -> Dict[str, Any]: ...

    def head_object(self, *, bucket: str, key: str) -> Dict[str, Any]: ...

    def delete_object(self, *, bucket: str, key: str) -> None: ...

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> Dict[str, Any]: ...


class NullStorageAdapter:
    """Fallback adapter that signals the storage backend is not configured."""

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: Dict[str, str]) -> Dict[str, Any]:  # noqa: D401
        raise RuntimeError("storage_adapter_not_configured")

    def head_object(self, *, bucket: str, key: str) -> Dict[str, Any]:  # noqa: D401
        raise RuntimeError("storage_adapter_not_configured")

    def delete_object(self, *, bucket: str, key: str) -> None:  # noqa: D401
        raise RuntimeError("storage_adapter_not_configured")

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> Dict[str, Any]:  # noqa: D401
        raise RuntimeError("storage_adapter_not_configured")


__all__ = ["StorageAdapterProtocol", "NullStorageAdapter"]
