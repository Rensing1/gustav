import re


def test_openapi_marks_dev_only_paths_and_removes_dev_hint():
    """
    Contract check for dev-only markers and public descriptions.

    - Ensures internal upload helpers are marked with x-internal: true.
    - Ensures public schemas do not mention dev-only stub endpoints.
    """
    text = open("api/openapi.yml", "r", encoding="utf-8").read()

    # upload-stub must be marked x-internal: true
    assert re.search(r"/api/learning/internal/upload-stub:\n\s*x-internal:\s*true", text), (
        "upload-stub path missing x-internal: true"
    )

    # upload-proxy must be marked x-internal: true
    assert re.search(r"/api/learning/internal/upload-proxy:\n\s*x-internal:\s*true", text), (
        "upload-proxy path missing x-internal: true"
    )

    # Public field descriptions should not suggest dev-only stub URLs
    assert "In dev, a local stub path" not in text

