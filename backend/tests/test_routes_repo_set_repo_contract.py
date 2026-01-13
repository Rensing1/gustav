"""
Routes repo swapping contract.

Why:
    Several tests switch between DB-backed and in-memory repos via `set_repo(...)`.
    The public module attribute (`routes.<x>.REPO`) must reflect that change,
    because other tests use it for `isinstance(...)` guards.

    A mismatch causes order-dependent skips in full-suite runs.
"""

from __future__ import annotations


def test_teaching_set_repo_updates_public_repo_alias():
    import routes.teaching as teaching  # type: ignore

    original = teaching._get_repo()  # type: ignore[attr-defined]
    replacement = teaching._Repo()  # type: ignore[attr-defined]
    try:
        teaching.set_repo(replacement)  # type: ignore[attr-defined]
        assert teaching._get_repo() is replacement  # type: ignore[attr-defined]
        assert teaching.REPO is replacement  # type: ignore[attr-defined]
    finally:
        teaching.set_repo(original)  # type: ignore[attr-defined]


def test_learning_set_repo_updates_public_repo_alias():
    import routes.learning as learning  # type: ignore

    class _StubRepo:
        def list_released_sections(self, **kwargs):
            return []

        def create_submission(self, data):
            return {}

        def list_submissions(self, **kwargs):
            return []

    original = learning._get_repo()  # type: ignore[attr-defined]
    replacement = _StubRepo()
    try:
        learning.set_repo(replacement)  # type: ignore[attr-defined]
        assert learning._get_repo() is replacement  # type: ignore[attr-defined]
        assert learning.REPO is replacement  # type: ignore[attr-defined]
    finally:
        learning.set_repo(original)  # type: ignore[attr-defined]

