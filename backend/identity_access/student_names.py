"""Canonical teacher-visible name resolution with privacy-safe fallbacks."""

from __future__ import annotations


def resolve_student_names(subs: list[str]) -> dict[str, str]:
    """Resolve canonical teacher-visible learner labels via the directory.

    The directory already applies the shared `TeacherStudentLabel` contract.
    This shared adapter preserves its exact result and only derives a localpart
    from legacy email-like subjects when no directory record exists.
    """
    out: dict[str, str] = {}
    try:
        from backend.identity_access import directory  # type: ignore
        raw = directory.resolve_student_names(subs)
        for sid in subs:
            val = str((raw or {}).get(sid, "")).strip()
            if not val or val == sid:
                fallback = ""
                try:
                    if sid.startswith("legacy-email:") or ("@" in sid):
                        fallback = directory.localpart_identifier(sid)  # type: ignore[attr-defined]
                except Exception:
                    fallback = ""
                out[sid] = fallback or "Unbekannt"
            else:
                out[sid] = val
        return out
    except Exception:
        return {s: "Unbekannt" for s in subs}
