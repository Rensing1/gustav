"""Explicit DB, signing and bounded-download dependencies for learner materials."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import Protocol, cast

from fastapi import Request
from starlette.concurrency import run_in_threadpool

from backend.learning.repo_db import DBLearningRepo
from backend.storage.supabase_factory import build_storage_adapter as _build_storage_adapter
from backend.teaching.storage import StorageAdapterProtocol
from backend.web.material_file_access import (
    StudentMaterialAssetMetadata,
    StudentMaterialFileMetadata,
    load_student_material_asset_metadata,
    load_student_material_file_metadata,
)
from backend.web.routes.learning_downloads import download_bytes_with_limit


class ByteDownloader(Protocol):
    async def __call__(
        self, *, url: str, max_bytes: int, headers: dict[str, str] | None
    ) -> bytes | None: ...


@dataclass(frozen=True)
class LearningMaterialProviders:
    repository: Callable[[], object]
    storage: Callable[[], StorageAdapterProtocol | None]
    download: ByteDownloader

    def file_metadata(
        self, *, student_sub: str, course_id: str, material_id: str
    ) -> StudentMaterialFileMetadata | None:
        """Read current file visibility; caller runs the whole DB operation in the threadpool."""
        return load_student_material_file_metadata(
            repo=self.repository(),
            student_sub=student_sub,
            course_id=course_id,
            material_id=material_id,
        )

    def asset_metadata(
        self, *, student_sub: str, course_id: str, material_id: str
    ) -> StudentMaterialAssetMetadata | None:
        """Read current asset visibility, including simulation kind and MIME type."""
        return load_student_material_asset_metadata(
            repo=self.repository(),
            student_sub=student_sub,
            course_id=course_id,
            material_id=material_id,
        )

    def _presign(self, *, bucket: str, key: str, disposition: str) -> dict | None:
        """Sign only after authorization; storage initialization/signing may block."""
        try:
            adapter = self.storage()
            if not bucket or adapter is None:
                return None
            return adapter.presign_download(
                bucket=bucket, key=key, expires_in=60, disposition=disposition
            )
        except Exception:
            return None

    async def download_object(
        self, *, bucket: str, key: str, disposition: str, max_bytes: int
    ) -> bytes | None:
        """Fetch an authorized object without exposing its signed URL to the browser.

        The caller must first confirm current material visibility. Only synchronous
        initialization/signing runs in the threadpool; the bounded HTTP fetch
        remains asynchronous and uses the established origin/redirect guards.
        """
        presigned = await run_in_threadpool(
            self._presign, bucket=bucket, key=key, disposition=disposition
        )
        if not isinstance(presigned, dict):
            return None
        url = str(presigned.get("url") or "").strip()
        if not url:
            return None
        try:
            headers = {
                str(k): str(v) for k, v in dict(presigned.get("headers") or {}).items() if k and v
            }
        except Exception:
            headers = None
        return await self.download(url=url, max_bytes=max_bytes, headers=headers)




def create_learning_material_providers(
    *, environment: Callable[[], str]
) -> LearningMaterialProviders:
    """Construct dependencies lazily within authorized reads; failures stay retryable."""

    @cache
    def repository():
        return DBLearningRepo()

    @cache
    def storage():
        return _build_storage_adapter()

    async def download(*, url: str, max_bytes: int, headers: dict[str, str] | None):
        return await download_bytes_with_limit(
            url=url, max_bytes=max_bytes, headers=headers, environment=environment()
        )

    return LearningMaterialProviders(repository=repository, storage=storage, download=download)


def learning_material_providers(request: Request) -> LearningMaterialProviders:
    """Resolve the dependencies installed during this backend's construction."""
    return cast(LearningMaterialProviders, request.app.state.learning_material_providers)
