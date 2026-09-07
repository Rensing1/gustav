"""Explicit transport and telemetry dependencies for the internal upload proxy."""

from dataclasses import dataclass
from typing import Protocol, cast

import httpx
from fastapi import Request

from backend.web.routes.learning_upload_proxy import (
    async_forward_upload,
    emit_upload_proxy_telemetry,
)


class UploadForwarder(Protocol):
    async def __call__(
        self,
        *,
        url: str,
        payload: bytes,
        content_type: str,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response: ...


class UploadTelemetry(Protocol):
    def __call__(
        self,
        *,
        outcome: str,
        status_code: int,
        reason: str,
        target_host: str,
        content_type: str,
        size_bytes: int | None,
    ) -> None: ...


@dataclass(frozen=True)
class LearningUploadProxyProviders:
    """The route validates identity, origin, target and body before forwarding."""

    forward: UploadForwarder
    emit: UploadTelemetry


def create_learning_upload_proxy_providers() -> LearningUploadProxyProviders:
    """Use the existing asynchronous HTTP transport and best-effort telemetry.

    Construction performs no network I/O. The transport owns its HTTP client per
    upload; no module reload lookup or shared endpoint mutation is needed.
    """
    return LearningUploadProxyProviders(
        forward=async_forward_upload, emit=emit_upload_proxy_telemetry
    )


def learning_upload_proxy_providers(request: Request) -> LearningUploadProxyProviders:
    """Resolve dependencies installed when the GUSTAV backend starts."""
    return cast(LearningUploadProxyProviders, request.app.state.learning_upload_proxy_providers)
