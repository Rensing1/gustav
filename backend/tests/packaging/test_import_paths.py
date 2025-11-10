"""Packaging sanity checks for import paths.

Ensures subpackages introduced by recent changes are importable under Docker
as well as local test runs.
"""
from importlib import import_module


def test_import_backend_vision_pipeline():
    mod = import_module("backend.vision.pipeline")
    assert hasattr(mod, "stitch_images_vertically")

