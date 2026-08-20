"""CLI entrypoint and orchestration for local/remote authoring synchronization."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from .config import GustavCLIConfig, load_config
from .sync_engine import ChangeOrigin, compare_digests, requires_prune, snapshot_digest
from .sync_manifest import load_local_snapshot, write_local_snapshot
from .sync_remote import GustavSyncClient

MISSING_UNIT_DIGEST = snapshot_digest(None)


def _load_state(root: Path) -> dict[str, Any]:
    _require_private_directory(root / ".gustav")
    path = root / ".gustav" / "state.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("sync_state_missing_or_invalid") from exc
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("sync_state_missing_or_invalid")
    return state


def _load_push_journal(root: Path, *, source_digest: str) -> dict[str, Any] | None:
    """Load a resumable push journal and bind it to the unchanged local source."""

    _require_private_directory(root / ".gustav")
    path = root / ".gustav" / "journal.json"
    if not path.exists():
        return None
    try:
        journal = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("sync_journal_invalid") from exc
    if (
        not isinstance(journal, dict)
        or journal.get("schema_version") != 1
        or journal.get("direction") != "push"
        or not isinstance(journal.get("mapping"), dict)
        or not isinstance(journal.get("observed_remote_digest"), str)
    ):
        raise ValueError("sync_journal_invalid")
    if journal.get("source_digest") != source_digest:
        raise ValueError("sync_journal_source_changed")
    return journal


def _save_json(path: Path, payload: object) -> None:
    """Atomically persist private sync metadata with restrictive permissions."""

    _ensure_private_directory(path.parent)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _ensure_private_directory(path: Path) -> None:
    """Create a private directory without following an existing symlink ancestor."""

    missing: list[Path] = []
    current = path
    while not current.exists():
        if current.is_symlink():
            raise ValueError("unsafe_private_sync_path")
        missing.append(current)
        if current == current.parent:
            break
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise ValueError("unsafe_private_sync_path")
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("unsafe_private_sync_path")


def _require_private_directory(path: Path) -> None:
    """Reject missing, symlinked, or non-directory private sync metadata roots."""

    if path.is_symlink() or not path.is_dir():
        raise ValueError("unsafe_private_sync_path")


def _save_state(
    root: Path,
    *,
    config: GustavCLIConfig,
    owner_sub: str,
    snapshot: dict[str, Any],
    mapping: dict[str, Any],
    previous_unit_digests: dict[str, str] | None = None,
    selected_keys: set[str] | None = None,
) -> None:
    unit_digests = dict(previous_unit_digests or {})
    units = snapshot.get("units", {})
    if not isinstance(units, dict):
        raise ValueError("invalid_units")
    if selected_keys is None:
        unit_digests = {str(key): snapshot_digest(unit) for key, unit in units.items()}
    else:
        for key in selected_keys:
            unit_digests[key] = snapshot_digest(units.get(key))
    _save_json(
        root / ".gustav" / "state.json",
        {
            "schema_version": 1,
            "base_url": config.base_url,
            "owner_sub": owner_sub,
            "base_digest": snapshot_digest(snapshot),
            "base_unit_digests": unit_digests,
            "mapping": mapping,
        },
    )


def _snapshot_result(result: object) -> tuple[dict[str, Any], dict[str, Any]]:
    """Accept the public `(snapshot, mapping)` reader shape and old test doubles."""

    if isinstance(result, tuple) and len(result) == 2:
        snapshot, mapping = result
    else:
        snapshot, mapping = result, {}
    if not isinstance(snapshot, dict) or not isinstance(mapping, dict):
        raise ValueError("invalid_remote_snapshot")
    return snapshot, mapping


def _resolve_selected_keys(
    selectors: list[str],
    *,
    local: dict[str, Any],
    remote: dict[str, Any],
    mapping: dict[str, Any],
) -> set[str] | None:
    """Resolve optional unit keys or remote ids without silently skipping typos."""

    if not selectors:
        return None
    local_units = local.get("units", {})
    remote_units = remote.get("units", {})
    unit_mapping = mapping.get("units", {})
    if not all(isinstance(value, dict) for value in (local_units, remote_units, unit_mapping)):
        raise ValueError("invalid_units")
    remote_ids = {
        str(entry.get("remote_id")): str(key)
        for key, entry in unit_mapping.items()
        if isinstance(entry, dict) and entry.get("remote_id")
    }
    known_keys = set(local_units) | set(remote_units) | set(unit_mapping)
    selected: set[str] = set()
    for selector in selectors:
        key = selector if selector in known_keys else remote_ids.get(selector)
        if key is None:
            raise ValueError(f"unknown_unit:{selector}")
        selected.add(key)
    return selected


def _scoped_snapshot(snapshot: dict[str, Any], selected_keys: set[str]) -> dict[str, Any]:
    units = snapshot.get("units", {})
    if not isinstance(units, dict):
        raise ValueError("invalid_units")
    return {
        "schema_version": 1,
        "units": {key: deepcopy(units[key]) for key in selected_keys if key in units},
    }


def _merge_selected_units(
    target: dict[str, Any], source: dict[str, Any], selected_keys: set[str]
) -> dict[str, Any]:
    merged = deepcopy(target)
    target_units = merged.get("units", {})
    source_units = source.get("units", {})
    if not isinstance(target_units, dict) or not isinstance(source_units, dict):
        raise ValueError("invalid_units")
    for key in selected_keys:
        if key in source_units:
            target_units[key] = deepcopy(source_units[key])
        else:
            target_units.pop(key, None)
    return merged


def _compare_sync_state(
    state: dict[str, Any],
    local: dict[str, Any],
    remote: dict[str, Any],
    selected_keys: set[str] | None,
):  # noqa: ANN202
    """Compare selected units against per-unit bases, with legacy-state fallback."""

    base_units = state.get("base_unit_digests")
    if not isinstance(base_units, dict):
        if selected_keys is not None:
            raise ValueError("unit_filter_requires_fresh_pull")
        return compare_digests(
            str(state.get("base_digest") or ""),
            snapshot_digest(local),
            snapshot_digest(remote),
        )
    local_units = local.get("units", {})
    remote_units = remote.get("units", {})
    if not isinstance(local_units, dict) or not isinstance(remote_units, dict):
        raise ValueError("invalid_units")
    keys = selected_keys or (set(base_units) | set(local_units) | set(remote_units))
    base_index = {key: str(base_units.get(key) or MISSING_UNIT_DIGEST) for key in keys}
    local_index = {key: snapshot_digest(local_units.get(key)) for key in keys}
    remote_index = {key: snapshot_digest(remote_units.get(key)) for key in keys}
    return compare_digests(
        snapshot_digest(base_index),
        snapshot_digest(local_index),
        snapshot_digest(remote_index),
    )


def _install_pull_snapshot(
    root: Path,
    snapshot: dict[str, Any],
    *,
    config: GustavCLIConfig,
    owner_sub: str,
    state_snapshot: dict[str, Any],
    mapping: dict[str, Any],
    previous_unit_digests: dict[str, str] | None = None,
    selected_keys: set[str] | None = None,
    keep_previous_units: bool = False,
) -> None:
    """Stage and validate a complete mirror before replacing the active directory."""

    root_parent = root.parent
    root_parent.mkdir(parents=True, exist_ok=True)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("unsafe_local_path")
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.gustav-staging-", dir=root_parent))
    backup_container: Path | None = None
    try:
        if root.exists():
            # Preserve user-added files and prior private trash, but replace the managed unit tree.
            shutil.copytree(root, staging, dirs_exist_ok=True, symlinks=True)
            staged_units = staging / "units"
            if staged_units.is_symlink():
                raise ValueError("unsafe_local_path")
            if staged_units.exists():
                shutil.rmtree(staged_units)
            if keep_previous_units and (root / "units").is_dir():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                trash_units = staging / ".gustav" / "trash" / stamp / "units"
                _ensure_private_directory(trash_units.parent)
                shutil.copytree(root / "units", trash_units, symlinks=True)

        write_local_snapshot(staging, snapshot, base_url=config.base_url)
        _save_state(
            staging,
            config=config,
            owner_sub=owner_sub,
            snapshot=state_snapshot,
            mapping=mapping,
            previous_unit_digests=previous_unit_digests,
            selected_keys=selected_keys,
        )
        staged_snapshot = load_local_snapshot(staging, expected_base_url=config.base_url)
        if snapshot_digest(staged_snapshot) != snapshot_digest(snapshot):
            raise ValueError("staged_pull_verification_failed")

        if not root.exists():
            os.replace(staging, root)
            return

        backup_container = Path(
            tempfile.mkdtemp(prefix=f".{root.name}.gustav-backup-", dir=root_parent)
        )
        backup_root = backup_container / "mirror"
        os.replace(root, backup_root)
        try:
            os.replace(staging, root)
        except Exception:
            os.replace(backup_root, root)
            raise
        shutil.rmtree(backup_container)
        backup_container = None
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup_container is not None and backup_container.exists():
            shutil.rmtree(backup_container)


def _write_report(report: dict[str, Any], *, as_json: bool, stdout: TextIO) -> None:
    if as_json:
        stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")
        return
    stdout.write(f"Status: {report['origin']}\n")
    if report["pull_blocked"]:
        stdout.write("Pull blockiert: Der lokale Spiegel enthält Änderungen.\n")
    if report["push_blocked"]:
        stdout.write("Push blockiert: Die externe Lerneinheit enthält Änderungen.\n")


def run_sync(args, *, stdout: TextIO, stderr: TextIO) -> int:  # noqa: ANN001
    """Run one sync subcommand without exposing tokens or authored content."""

    try:
        cfg = load_config()
        root = Path(args.root)
        client = GustavSyncClient(cfg)
        if args.command == "pull" and not (root / ".gustav" / "state.json").exists():
            if root.exists() and any(root.iterdir()):
                raise ValueError("unmanaged_mirror_not_empty")
            owner_sub = client.read_owner_sub()
            remote, mapping = _snapshot_result(client.fetch_snapshot({}, include_assets=True))
            selected_keys = _resolve_selected_keys(
                args.unit,
                local={"schema_version": 1, "units": {}},
                remote=remote,
                mapping=mapping,
            )
            local_target = (
                _scoped_snapshot(remote, selected_keys) if selected_keys is not None else remote
            )
            _install_pull_snapshot(
                root,
                local_target,
                config=cfg,
                owner_sub=owner_sub,
                state_snapshot=remote,
                mapping=mapping,
                selected_keys=selected_keys,
            )
            report = {"origin": "remote", "pull_blocked": False, "push_blocked": False}
            _write_report(report, as_json=args.json, stdout=stdout)
            return 0
        state = _load_state(root)
        if state.get("base_url") != cfg.base_url:
            raise ValueError("mirror_binding_mismatch")
        local = load_local_snapshot(root, expected_base_url=cfg.base_url)
        local_digest = snapshot_digest(local)
        owner_sub = client.read_owner_sub()
        if state.get("owner_sub") != owner_sub:
            raise ValueError("mirror_owner_mismatch")
        journal = (
            _load_push_journal(root, source_digest=local_digest) if args.command == "push" else None
        )
        mapping = dict((journal or state).get("mapping") or {})
        remote, refreshed_mapping = _snapshot_result(client.fetch_snapshot(mapping))
        remote_digest = snapshot_digest(remote)
        selected_keys = _resolve_selected_keys(
            args.unit,
            local=local,
            remote=remote,
            mapping=refreshed_mapping,
        )
        local_scope = _scoped_snapshot(local, selected_keys) if selected_keys is not None else local
        remote_scope = (
            _scoped_snapshot(remote, selected_keys) if selected_keys is not None else remote
        )
        resumes_verified_push = bool(
            journal and journal.get("observed_remote_digest") == remote_digest
        )
        comparison = _compare_sync_state(state, local, remote, selected_keys)
        if args.command == "pull":
            if (
                comparison.origin in {ChangeOrigin.LOCAL, ChangeOrigin.DIVERGED}
                and not args.discard_local
            ):
                stderr.write(
                    "Pull blockiert: lokale Änderungen würden überschrieben; "
                    "bewusste Auflösung erfordert --discard-local.\n"
                )
                return 1
            needs_prune = requires_prune(remote_scope, local_scope)
            if needs_prune and not args.prune:
                stderr.write("Pull enthält Löschungen; Ausführung erfordert --prune.\n")
                return 1
            remote_with_assets, refreshed_mapping = _snapshot_result(
                client.fetch_snapshot(refreshed_mapping, include_assets=True)
            )
            local_target = (
                _merge_selected_units(local, remote_with_assets, selected_keys)
                if selected_keys is not None
                else remote_with_assets
            )
            _install_pull_snapshot(
                root,
                local_target,
                config=cfg,
                owner_sub=owner_sub,
                state_snapshot=remote_with_assets,
                mapping=refreshed_mapping,
                previous_unit_digests=state.get("base_unit_digests"),
                selected_keys=selected_keys,
                keep_previous_units=needs_prune,
            )
        elif args.command == "push":
            if args.prune and not args.yes:
                stderr.write("Remote-Löschungen erfordern --prune und --yes.\n")
                return 1
            if (
                comparison.origin in {ChangeOrigin.REMOTE, ChangeOrigin.DIVERGED}
                and not args.overwrite_remote
                and not resumes_verified_push
            ):
                stderr.write(
                    "Push blockiert: externe Änderungen würden überschrieben; "
                    "bewusste Auflösung erfordert --overwrite-remote.\n"
                )
                return 1
            if requires_prune(local_scope, remote_scope) and not args.prune:
                stderr.write("Push enthält Löschungen; Ausführung erfordert --prune und --yes.\n")
                return 1
            journal_path = root / ".gustav" / "journal.json"

            def checkpoint(current_mapping: dict[str, Any]) -> None:
                observed, observed_mapping = _snapshot_result(
                    client.fetch_snapshot(current_mapping)
                )
                _save_json(
                    journal_path,
                    {
                        "schema_version": 1,
                        "direction": "push",
                        "source_digest": local_digest,
                        "observed_remote_digest": snapshot_digest(observed),
                        "mapping": observed_mapping,
                    },
                )

            checkpoint(refreshed_mapping)

            observed_units = remote_scope.get("units", {})
            if not isinstance(observed_units, dict):
                raise ValueError("invalid_remote_snapshot")

            def verify_unit_unchanged(
                unit_key: str, current_mapping: dict[str, Any]
            ) -> None:
                latest, latest_mapping = _snapshot_result(client.fetch_snapshot(current_mapping))
                latest_units = latest.get("units", {})
                if not isinstance(latest_units, dict):
                    raise ValueError("invalid_remote_snapshot")
                if snapshot_digest(latest_units.get(unit_key)) != snapshot_digest(
                    observed_units.get(unit_key)
                ):
                    raise ValueError(f"remote_unit_changed_during_push:{unit_key}")
                current_mapping.clear()
                current_mapping.update(latest_mapping)

            refreshed_mapping = client.push_snapshot(
                local_scope,
                remote_scope,
                refreshed_mapping,
                prune=args.prune,
                checkpoint=checkpoint,
                before_unit=verify_unit_unchanged,
            )
            verified, refreshed_mapping = _snapshot_result(client.fetch_snapshot(refreshed_mapping))
            verified_scope = (
                _scoped_snapshot(verified, selected_keys) if selected_keys is not None else verified
            )
            if snapshot_digest(verified_scope) != snapshot_digest(local_scope):
                raise ValueError("push_verification_failed")
            _save_state(
                root,
                config=cfg,
                owner_sub=owner_sub,
                snapshot=verified,
                mapping=refreshed_mapping,
                previous_unit_digests=state.get("base_unit_digests"),
                selected_keys=selected_keys,
            )
            journal_path.unlink(missing_ok=True)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        stderr.write(f"Sync-Fehler: {exc}\n")
        return 1
    report = {
        "origin": comparison.origin.value,
        "pull_blocked": comparison.origin in {ChangeOrigin.LOCAL, ChangeOrigin.DIVERGED},
        "push_blocked": comparison.origin in {ChangeOrigin.REMOTE, ChangeOrigin.DIVERGED},
    }
    _write_report(report, as_json=args.json, stdout=stdout)
    if args.command == "status":
        return 0 if comparison.origin is ChangeOrigin.CLEAN else 2
    return 0
