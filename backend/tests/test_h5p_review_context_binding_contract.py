"""Source contract for task-bound H5P review user-state requests."""

from pathlib import Path


def test_review_user_state_url_uses_controller_context_id() -> None:
    """Lumi's controller forwards `contextId`, so review URLs must use that name."""

    root = Path(__file__).resolve().parents[2]
    source = (root / "h5p-service" / "server.mjs").read_text(encoding="utf-8")
    start = source.index('app.get("/player/review"')
    end = source.index('app.post("/contents"', start)
    review_route = source[start:end]

    assert 'u.searchParams.set("contextId", String(contextId));' in review_route
    assert 'u.searchParams.set("context_id", String(contextId));' not in review_route
