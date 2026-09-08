"""Submission input rules can be exercised without loading a web framework."""

import pytest


def validate(payload, limit=10):
    from backend.learning.submission_payload import validate_submission_payload

    return validate_submission_payload(payload, max_upload_bytes=limit)


@pytest.mark.parametrize("text,valid", [(" a ", True), (" ", False), ("a" * 65536, True), ("a" * 65537, False), (None, False)], ids=["trim", "empty", "maximum", "too-long", "null"])
def test_text_boundaries(text, valid):
    if valid:
        assert validate({"kind": "text", "text_body": text}) == ("text", {"intent": "submit", "text_body": text.strip()})
    else:
        with pytest.raises(ValueError, match="invalid_input"):
            validate({"kind": "text", "text_body": text})


@pytest.mark.parametrize("raw,maximum,valid", [(0, 0, True), (2, 3, True), (3, 2, False), (-1, 2, False), ("bad", 2, False)])
def test_h5p_score_bounds(raw, maximum, valid):
    payload = {"kind": "h5p", "score_raw": raw, "score_max": maximum}
    if valid:
        assert validate(payload)[1] == {"intent": "submit", "score_raw": raw, "score_max": maximum}
    else:
        with pytest.raises(ValueError, match="invalid_h5p_payload"):
            validate(payload)


@pytest.mark.parametrize("size,valid", [(0, False), (1, True), (10, True), (11, False)])
def test_explicit_upload_limit_and_normalization(size, valid):
    payload = {"kind": "image", "storage_key": "submissions/course/task/student/file.png", "mime_type": "IMAGE/PNG", "size_bytes": size, "sha256": "A" * 64}
    if valid:
        kind, clean = validate(payload)
        assert kind == "image" and clean["mime_type"] == "image/png"
        assert clean["sha256"] == "a" * 64
    else:
        with pytest.raises(ValueError, match="invalid_image_payload"):
            validate(payload)
