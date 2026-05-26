import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = PROJECT_ROOT / "Makefile"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    target_name = re.escape(target)
    match = re.search(
        rf"(?ms)^\.PHONY: {target_name}\n{target_name}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_reset_local_provisions_worker_login_before_recreating_worker() -> None:
    body = _target_body("reset-local")

    assert "$(MAKE) db-login-user" in body
    assert "$(MAKE) learning-worker-db-login-user" in body
    assert "docker compose up -d --build --force-recreate web learning-worker h5p" in body
    assert body.index("$(MAKE) db-login-user") < body.index(
        "$(MAKE) learning-worker-db-login-user"
    )
    assert body.index("$(MAKE) learning-worker-db-login-user") < body.index(
        "docker compose up -d --build --force-recreate web learning-worker h5p"
    )
