"""
OpenAPI contract tests for Teaching paths (regression for path placement).

Validates that DELETE /api/teaching/units/{unit_id} is defined under the
correct path and not accidentally nested under the sections/reorder path.
Also checks that Unit PATCH uses authorOnly permission semantics.
"""
from __future__ import annotations

from pathlib import Path
import yaml


def test_units_delete_path_is_correct_and_not_under_reorder():
    root = Path(__file__).resolve().parents[2]
    yml = (root / "api" / "openapi.yml").read_text(encoding="utf-8")
    spec = yaml.safe_load(yml)

    paths = spec.get("paths", {})
    # DELETE must exist under /api/teaching/units/{unit_id}
    unit_path = "/api/teaching/units/{unit_id}"
    assert unit_path in paths, "units path missing in OpenAPI"
    assert "delete" in paths[unit_path], "DELETE missing for units in OpenAPI"

    # DELETE must not be placed under sections/reorder
    reorder_path = "/api/teaching/units/{unit_id}/sections/reorder"
    assert reorder_path in paths, "reorder path missing in OpenAPI"
    assert "delete" not in paths[reorder_path], "Unexpected DELETE under sections/reorder"


def test_units_patch_uses_author_permission_semantics():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    unit_path = "/api/teaching/units/{unit_id}"
    perms = spec["paths"][unit_path]["patch"].get("x-permissions", {})
    # authorOnly should be used for units, not ownerOnly
    assert perms.get("requiredRole") == "teacher"
    assert perms.get("authorOnly") is True
    assert "ownerOnly" not in perms


def test_sections_reorder_includes_section_mismatch_detail():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))
    path = "/api/teaching/units/{unit_id}/sections/reorder"
    errs = spec["paths"][path]["post"]["responses"]["400"]["description"]
    # Expect the section_mismatch detail to be listed among error codes
    assert "section_mismatch" in errs


def test_reorder_examples_present_in_openapi():
    root = Path(__file__).resolve().parents[2]
    spec = yaml.safe_load((root / "api" / "openapi.yml").read_text(encoding="utf-8"))

    # Sections reorder examples
    sec_path = "/api/teaching/units/{unit_id}/sections/reorder"
    sec_examples = spec["paths"][sec_path]["post"]["responses"]["400"]["content"]["application/json"]["examples"]
    for key in [
        "section_mismatch",
        "duplicate_section_ids",
        "invalid_section_ids",
        "empty_section_ids",
        "section_ids_must_be_array",
    ]:
        assert key in sec_examples

    # Course modules reorder examples
    mod_path = "/api/teaching/courses/{course_id}/modules/reorder"
    mod_examples = spec["paths"][mod_path]["post"]["responses"]["400"]["content"]["application/json"]["examples"]
    for key in [
        "duplicate_module_ids",
        "module_mismatch",
        "empty_reorder",
        "invalid_module_ids",
        "no_modules",
    ]:
        assert key in mod_examples
