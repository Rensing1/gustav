"""Check the OpenAPI baseline against the runtime API route surface."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
import sys
from pathlib import Path
from typing import Any

import yaml


HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
PATH_CONVERTER_RE = re.compile(r"\{([^}:]+):[^}]+\}")
SURFACES = (
    "public API",
    "BFF/internal",
    "H5P service",
    "auth bridge",
    "health/ops",
    "active legacy UI",
    "retired legacy UI",
)


@dataclass(frozen=True, order=True)
class Operation:
    method: str
    path: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_path(path: str) -> str:
    """Normalize FastAPI path converters to OpenAPI path parameters."""

    return PATH_CONVERTER_RE.sub(r"{\1}", path)


def classify_surface(path: str) -> str:
    """Classify the route surface used by contract governance."""

    if path.startswith("/h5p/"):
        return "H5P service"
    if path == "/health" or path.startswith("/internal/health/"):
        return "health/ops"
    if path.startswith("/auth/"):
        return "auth bridge"
    if path.startswith("/backend-internal/"):
        return "BFF/internal"
    if path.startswith("/api/app/") or "/views/" in path:
        return "BFF/internal"
    if path.startswith("/api/learning/internal/"):
        return "BFF/internal"
    if path.startswith("/api/learning/concern-box/") or path.startswith("/api/teaching/concern-box/"):
        return "BFF/internal"
    if path.startswith("/api/"):
        return "public API"
    if path.startswith(("/courses", "/learning", "/teaching", "/units", "/fragments", "/about")) or path == "/":
        return "active legacy UI"
    return "retired legacy UI"


def openapi_operations(spec_path: Path) -> set[Operation]:
    """Return operations declared by the static OpenAPI document."""

    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    paths = spec.get("paths", {})
    operations: set[Operation] = set()
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method in methods:
            upper = str(method).upper()
            if upper in HTTP_METHODS:
                operations.add(Operation(upper, normalize_path(str(path))))
    return operations


def runtime_operations() -> set[Operation]:
    """Return operations registered by the FastAPI app at import time."""

    from fastapi.routing import APIRoute

    from backend.web.main import app

    operations: set[Operation] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            upper = str(method).upper()
            if upper in HTTP_METHODS:
                operations.add(Operation(upper, normalize_path(route.path)))
    return operations


def check_contract(spec_path: Path) -> list[str]:
    """Return human-readable contract violations."""

    spec_ops = openapi_operations(spec_path)
    runtime_ops = runtime_operations()
    spec_api = {op for op in spec_ops if op.path.startswith("/api/")}
    runtime_api = {op for op in runtime_ops if op.path.startswith("/api/")}

    violations: list[str] = []
    missing = sorted(runtime_api - spec_api)
    stale = sorted(spec_api - runtime_api)
    if missing:
        violations.append("Runtime /api/* operations missing from api/openapi.yml:")
        violations.extend(f"- {op.method} {op.path}" for op in missing)
    if stale:
        violations.append("api/openapi.yml /api/* operations missing from runtime app:")
        violations.extend(f"- {op.method} {op.path}" for op in stale)

    unknown_surfaces = sorted(
        op for op in (spec_ops | runtime_ops) if classify_surface(op.path) not in SURFACES
    )
    if unknown_surfaces:
        violations.append("Operations without a known route-surface classification:")
        violations.extend(f"- {op.method} {op.path}" for op in unknown_surfaces)

    return violations


def summary(spec_path: Path) -> dict[str, Any]:
    """Return route-surface counts for diagnostic output."""

    spec_ops = openapi_operations(spec_path)
    runtime_ops = runtime_operations()
    all_ops = spec_ops | runtime_ops
    counts = {surface: 0 for surface in SURFACES}
    for op in all_ops:
        counts[classify_surface(op.path)] += 1
    return {
        "openapi_operations": len(spec_ops),
        "runtime_operations": len(runtime_ops),
        "surfaces": counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=_repo_root() / "api" / "openapi.yml")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    violations = check_contract(args.spec)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    if args.summary:
        import json

        print(json.dumps(summary(args.spec), indent=2, sort_keys=True))
    print("openapi-contract-check-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
