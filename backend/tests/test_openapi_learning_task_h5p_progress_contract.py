"""Learning tasks expose the H5P progress needed for honest learner status."""

from pathlib import Path

import yaml


def test_learning_task_requires_h5p_completion_and_latest_score() -> None:
    spec = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "api" / "openapi.yml").read_text(encoding="utf-8")
    )
    schema = spec["components"]["schemas"]["LearningTask"]

    assert {"h5p_completed", "score_raw", "score_max"} <= set(schema["required"])
    properties = schema["properties"]
    assert properties["h5p_completed"]["nullable"] is True
    assert properties["score_raw"]["minimum"] == 0
    assert properties["score_max"]["minimum"] == 0
    assert "including 0/0" in properties["h5p_completed"]["description"]
