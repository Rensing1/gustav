"""Unit tests for the student-safe printable-unit application service."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.teaching.printouts import PrintExportError, create_printable_pdf


@dataclass
class _RenderedPdf:
    content: bytes = b"%PDF-safe"


class _Renderer:
    def __init__(self) -> None:
        self.document = None

    def render(self, document, *, policy):  # type: ignore[no-untyped-def]
        self.document = document
        return _RenderedPdf().content


class _Storage:
    def read_object(self, *, bucket: str, key: str, max_bytes: int) -> bytes:
        assert bucket == "materials"
        assert key == "owned/diagram.png"
        assert max_bytes == 52_428_800
        return b"image-bytes"


class _Repo:
    def get_unit_for_author(self, unit_id: str, author_id: str):  # type: ignore[no-untyped-def]
        if unit_id != "unit-1" or author_id != "teacher-1":
            return None
        return {"id": unit_id, "title": "Netzwerke", "unit_type": "linear"}

    def list_sections_for_author(self, unit_id: str, author_id: str):  # type: ignore[no-untyped-def]
        assert (unit_id, author_id) == ("unit-1", "teacher-1")
        return [{"id": "section-1", "title": "Einstieg", "position": 1}]

    def list_materials_for_section_owned(self, unit_id: str, section_id: str, author_id: str):  # type: ignore[no-untyped-def]
        assert (unit_id, section_id, author_id) == ("unit-1", "section-1", "teacher-1")
        return [
            {
                "id": "material-markdown",
                "title": "Merkblatt",
                "body_md": "Ein [Link](https://example.org) erklärt das Netz.",
                "kind": "markdown",
                "position": 1,
            },
            {
                "id": "material-image",
                "title": "Topologie",
                "body_md": "Beschreibe die Abbildung.",
                "kind": "file",
                "position": 2,
                "storage_key": "owned/diagram.png",
                "filename_original": "diagram.png",
                "mime_type": "image/png",
                "size_bytes": 11,
                "alt_text": "Sternförmiges Netzwerk",
            },
        ]

    def list_tasks_for_section_owned(self, unit_id: str, section_id: str, author_id: str):  # type: ignore[no-untyped-def]
        assert (unit_id, section_id, author_id) == ("unit-1", "section-1", "teacher-1")
        return [
            {
                "id": "task-1",
                "instruction_md": "Erkläre das **Netzwerk**.",
                "criteria": ["internes Kriterium"],
                "teacher_context_md": "nur für Lehrkräfte",
                "model_solution_md": "geheime Musterlösung",
                "due_at": "2026-09-10T08:00:00+00:00",
                "max_attempts": 2,
                "kind": "h5p",
                "position": 1,
            }
        ]


def test_export_prepares_ordered_student_copy_without_teacher_only_fields() -> None:
    renderer = _Renderer()

    result = create_printable_pdf(
        _Repo(),
        storage=_Storage(),
        renderer=renderer,
        unit_id="unit-1",
        author_id="teacher-1",
        material_ids=["material-image", "material-markdown"],
        task_ids=["task-1"],
        storage_bucket="materials",
    )

    assert result.content == b"%PDF-safe"
    assert result.filename == "gustav-netzwerke-druckfassung.pdf"
    assert renderer.document == {
        "title": "Netzwerke",
        "nodes": [
            {
                "title": "Einstieg",
                "items": [
                    {
                        "type": "markdown",
                        "title": "Merkblatt",
                        "body_md": "Ein [Link](https://example.org) erklärt das Netz.",
                    },
                    {
                        "type": "image",
                        "title": "Topologie",
                        "body_md": "Beschreibe die Abbildung.",
                        "filename": "diagram.png",
                        "mime_type": "image/png",
                        "alt_text": "Sternförmiges Netzwerk",
                        "content": b"image-bytes",
                    },
                    {
                        "type": "task",
                        "title": "Aufgabe",
                        "body_md": "Erkläre das **Netzwerk**.",
                        "digital_hint": "Für die interaktive Bearbeitung wird ein digitales Gerät benötigt.",
                    },
                ],
            }
        ],
    }
    serialized = repr(renderer.document)
    assert "Musterlösung" not in serialized
    assert "Lehrkräfte" not in serialized
    assert "Kriterium" not in serialized
    assert "2026-09-10" not in serialized


def test_export_rejects_unknown_or_cross_unit_selection_without_disclosure() -> None:
    with pytest.raises(PrintExportError) as error:
        create_printable_pdf(
            _Repo(),
            storage=_Storage(),
            renderer=_Renderer(),
            unit_id="unit-1",
            author_id="teacher-1",
            material_ids=["material-from-another-unit"],
            task_ids=[],
            storage_bucket="materials",
        )

    assert error.value.code == "invalid_print_selection"
    assert error.value.status_code == 400


def test_export_fails_as_one_operation_when_a_selected_file_is_unavailable() -> None:
    class BrokenStorage(_Storage):
        def read_object(self, *, bucket: str, key: str, max_bytes: int) -> bytes:
            raise RuntimeError("storage_down")

    with pytest.raises(PrintExportError) as error:
        create_printable_pdf(
            _Repo(),
            storage=BrokenStorage(),
            renderer=_Renderer(),
            unit_id="unit-1",
            author_id="teacher-1",
            material_ids=["material-image"],
            task_ids=[],
            storage_bucket="materials",
        )

    assert error.value.code == "source_unavailable"
    assert error.value.status_code == 503
    assert error.value.material_title == "Topologie"


def test_export_uses_unit_wide_batch_reads_when_repository_supports_them() -> None:
    class BatchRepo(_Repo):
        def list_materials_for_unit_owned(self, unit_id: str, author_id: str):  # type: ignore[no-untyped-def]
            return [
                {**item, "section_id": "section-1"}
                for item in super().list_materials_for_section_owned(unit_id, "section-1", author_id)
            ]

        def list_tasks_for_unit_owned(self, unit_id: str, author_id: str):  # type: ignore[no-untyped-def]
            return [
                {**item, "section_id": "section-1"}
                for item in super().list_tasks_for_section_owned(unit_id, "section-1", author_id)
            ]

        def list_materials_for_section_owned(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("N+1 material read")

        def list_tasks_for_section_owned(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("N+1 task read")

    result = create_printable_pdf(
        BatchRepo(),
        storage=_Storage(),
        renderer=_Renderer(),
        unit_id="unit-1",
        author_id="teacher-1",
        material_ids=["material-markdown"],
        task_ids=["task-1"],
        storage_bucket="materials",
    )

    assert result.content.startswith(b"%PDF")
