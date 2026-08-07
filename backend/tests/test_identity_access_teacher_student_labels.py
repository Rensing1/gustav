"""Teacher-visible learner labels follow one privacy-safe contract."""

from __future__ import annotations

import importlib
import types

import pytest

from backend.identity_access import directory


# Route modules are loaded dynamically in adapter tests so the production
# dependency graph remains visible to the import-boundary scanner.
teaching = importlib.import_module("backend.web.routes.teaching")


@pytest.mark.parametrize(
    ("user", "expected"),
    [
        (
            {
                "firstName": "  Anna ",
                "lastName": " Adler  ",
                "email": "fallback@example.test",
                "attributes": {"display_name": ["Freier Anzeigename"]},
            },
            "Anna Adler",
        ),
        ({"firstName": "Anna", "lastName": "", "email": "Anna.Adler-10@example.test"}, "Anna.Adler-10"),
        ({"firstName": "", "lastName": "Adler", "email": "anna.adler@example.test"}, "anna.adler"),
        ({"username": "legacy-email:klasse-10a@example.test"}, "klasse-10a"),
        ({"username": "kein-email-identifier"}, "Unbekannt"),
        ({"id": "opaque-student-sub"}, "Unbekannt"),
    ],
)
def test_teacher_student_label_uses_complete_person_name_or_exact_localpart(
    user: dict[str, object],
    expected: str,
) -> None:
    assert directory.teacher_student_label(user) == expected


def test_resolve_student_names_uses_the_teacher_label_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(directory._KC, "token", lambda self: "token")

    class _Response:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "firstName": "Nurvorname",
                "lastName": "",
                "email": "konto.name@example.test",
                "attributes": {"display_name": ["Nicht verwenden"]},
            }

    monkeypatch.setattr(directory, "requests", types.SimpleNamespace(get=lambda *args, **kwargs: _Response()))

    assert directory.resolve_student_names(["opaque-sub"]) == {"opaque-sub": "konto.name"}


def test_teaching_wrapper_preserves_canonical_localpart(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(directory, "resolve_student_names", lambda subs: {str(subs[0]): "anna.adler"})

    assert teaching.resolve_student_names(["student-sub"]) == {"student-sub": "anna.adler"}


def test_teaching_wrapper_never_exposes_unresolved_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(directory, "resolve_student_names", lambda subs: {str(subs[0]): str(subs[0])})

    assert teaching.resolve_student_names(["opaque-student-sub"]) == {"opaque-student-sub": "Unbekannt"}
