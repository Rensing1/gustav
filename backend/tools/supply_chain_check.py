"""Offline supply-chain inventory and license-policy check.

The check is intentionally deterministic: it reads committed dependency
manifests and installed Python package metadata, then compares the result with
the committed inventory. It does not call package registries or vulnerability
databases because `make verify` must work without network access.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "docs/harness/SUPPLY_CHAIN_INVENTORY.json"

ALLOWED_LICENSES = {
    "0BSD",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BlueOak-1.0.0",
    "CC0-1.0",
    "EPL-2.0",
    "GPL-3.0",
    "GPL-3.0-or-later",
    "ISC",
    "MIT",
    "MIT-0",
    "MPL-2.0",
    "OFL-1.1",
    "Python-2.0",
    "Unlicense",
}

NODE_LICENSE_OVERRIDES = {
    ("h5p-service", "busboy"): "MIT",
    ("h5p-service", "esprima"): "BSD-2-Clause",
    ("h5p-service", "prelude-ls"): "MIT",
    ("h5p-service", "streamsearch"): "MIT",
}


def _json_dump(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _split_license_expression(raw: str) -> set[str]:
    cleaned = raw.replace("(", " ").replace(")", " ")
    return {part for part in re.split(r"\s+(?:OR|AND)\s+|\s+", cleaned) if part and part != "UNKNOWN"}


def _license_is_allowed(raw: str) -> bool:
    parts = _split_license_expression(raw)
    return bool(parts) and all(part in ALLOWED_LICENSES for part in parts)


def _requirement_name(line: str) -> str | None:
    without_comment = line.split("#", 1)[0].strip()
    if not without_comment:
        return None
    # Requirement options (`-r`, `--index-url`, `-e`, ...) configure pip and
    # are not package names. Included files are traversed separately above.
    if without_comment.startswith("-"):
        return None
    match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?", without_comment)
    return match.group(1).lower().replace("_", "-") if match else None


def _python_license_for(requirement_name: str) -> str:
    try:
        meta = metadata.metadata(requirement_name)
    except metadata.PackageNotFoundError:
        return "UNKNOWN"

    raw_license = str(meta.get("License") or "").strip()
    if raw_license and raw_license.upper() != "UNKNOWN":
        return raw_license

    classifiers = meta.get_all("Classifier") or []
    for classifier in classifiers:
        if classifier.startswith("License ::"):
            return classifier
    return "UNKNOWN"


def _requirement_files(manifest: Path, *, seen: set[Path] | None = None) -> list[Path]:
    """Return a manifest and all local `-r` includes exactly once."""

    resolved = manifest.resolve()
    visited = seen if seen is not None else set()
    if resolved in visited:
        return []
    visited.add(resolved)
    files = [resolved]
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        match = re.match(r"^(?:-r|--requirement)\s+(.+)$", line)
        if match:
            files.extend(_requirement_files(resolved.parent / match.group(1).strip(), seen=visited))
    return files


def _python_inventory() -> tuple[list[dict[str, Any]], list[Path]]:
    manifests = _requirement_files(REPO_ROOT / "backend/requirements-harness.txt")
    entries: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for requirements in manifests:
        for line in requirements.read_text(encoding="utf-8").splitlines():
            name = _requirement_name(line)
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            try:
                version = metadata.version(name)
            except metadata.PackageNotFoundError:
                version = "not-installed"
            license_value = _python_license_for(name)
            entries.append(
                {
                    "ecosystem": "python",
                    "name": name,
                    "version": version,
                    "license": license_value,
                    "policy": "metadata-recorded",
                }
            )
    return sorted(entries, key=lambda item: item["name"]), manifests


def _node_package_name(package_path: str) -> str:
    return package_path.split("node_modules/")[-1]


def _node_inventory(workspace: str, lockfile: Path) -> list[dict[str, Any]]:
    data = json.loads(lockfile.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    for package_path, package in data.get("packages", {}).items():
        if not package_path.startswith("node_modules/"):
            continue
        name = _node_package_name(package_path)
        version = str(package.get("version") or "")
        license_value = str(package.get("license") or "").strip()
        override = NODE_LICENSE_OVERRIDES.get((workspace, name))
        if override:
            license_value = override
        policy = "allowed" if _license_is_allowed(license_value) else "review-required"
        entries.append(
            {
                "ecosystem": "node",
                "workspace": workspace,
                "name": name,
                "version": version,
                "license": license_value or "UNKNOWN",
                "policy": policy,
            }
        )
    return sorted(entries, key=lambda item: (item["workspace"], item["name"], item["version"]))


def build_inventory() -> dict[str, Any]:
    frontend = _node_inventory("frontend", REPO_ROOT / "frontend/package-lock.json")
    h5p = _node_inventory("h5p-service", REPO_ROOT / "h5p-service/package-lock.json")
    python, python_manifests = _python_inventory()
    entries = [*python, *frontend, *h5p]
    review_required = [
        item
        for item in entries
        if item["ecosystem"] == "node" and item["policy"] != "allowed"
    ]
    return {
        "schema_version": 1,
        "sources": [
            *(path.relative_to(REPO_ROOT).as_posix() for path in python_manifests),
            "frontend/package-lock.json",
            "h5p-service/package-lock.json",
        ],
        "policy": {
            "mode": "offline-lockfile-and-installed-metadata",
            "allowed_licenses": sorted(ALLOWED_LICENSES),
            "node_license_overrides": [
                {"workspace": workspace, "name": name, "license": license_value}
                for (workspace, name), license_value in sorted(NODE_LICENSE_OVERRIDES.items())
            ],
        },
        "summary": {
            "total_entries": len(entries),
            "python_entries": len(python),
            "node_entries": len(frontend) + len(h5p),
            "review_required_entries": len(review_required),
        },
        "entries": entries,
    }


def check_inventory() -> int:
    expected = _json_dump(build_inventory())
    if not INVENTORY_PATH.exists():
        print(f"missing supply-chain inventory: {INVENTORY_PATH}", file=sys.stderr)
        return 1
    actual = INVENTORY_PATH.read_text(encoding="utf-8")
    if actual != expected:
        print(
            "supply-chain inventory is stale; run "
            "`python -m backend.tools.supply_chain_check --write`",
            file=sys.stderr,
        )
        return 1
    inventory = json.loads(actual)
    review_required = inventory.get("summary", {}).get("review_required_entries")
    if review_required:
        print(f"supply-chain inventory has {review_required} review-required node entries", file=sys.stderr)
        return 1
    print("supply-chain-check-ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the generated inventory")
    parser.add_argument("--check", action="store_true", help="check the committed inventory")
    args = parser.parse_args(argv)

    if args.write:
        INVENTORY_PATH.write_text(_json_dump(build_inventory()), encoding="utf-8")
        print(f"wrote {INVENTORY_PATH}")
        return 0
    return check_inventory()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
