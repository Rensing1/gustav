from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_teacher_units_catalog_view() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/teaching/views/units/catalog" in spec["paths"]

    schema = spec["components"]["schemas"]["TeacherUnitsCatalogView"]
    assert schema["required"] == [
        "user",
        "query",
        "sort",
        "result_count",
        "items",
        "create_href",
    ]

    item = spec["components"]["schemas"]["TeacherUnitsCatalogItem"]
    assert item["required"] == [
        "id",
        "title",
        "status_label",
        "status_tone",
        "courses_count",
        "courses",
        "updated_at",
        "href",
    ]
