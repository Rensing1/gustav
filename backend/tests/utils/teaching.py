"""Explicit prerequisites for legacy Teaching API tests using the real DB."""

import importlib

from backend.teaching.repo_db import DBTeachingRepo
from backend.tests.utils.db import require_db_or_skip


def require_teaching_db_repo() -> DBTeachingRepo:
    """Return the current DB adapter or expose invalid test wiring as a failure.

    Run the existing safe DB availability check first, preserving its strict
    failure or optional skip. Resolve the route module only at call time because
    older tests reload it. Never repair aliases or swap a repository here: a
    non-DB adapter with a reachable DB indicates broken test isolation.
    """
    require_db_or_skip()
    repo = importlib.import_module("backend.web.routes.teaching")._get_repo()
    assert isinstance(repo, DBTeachingRepo), "current Teaching repository must be DB-backed"
    return repo
