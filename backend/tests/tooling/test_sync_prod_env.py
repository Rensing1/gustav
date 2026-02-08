import importlib
from pathlib import Path


def _read_env_value(path: Path, key: str) -> str:
    prefix = f"{key}="
    for line in path.read_text().splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def test_main_generates_app_csrf_secret_when_placeholder(monkeypatch, tmp_path):
    envfile = tmp_path / ".env"
    envfile.write_text(
        "\n".join(
            [
                "GUSTAV_ENV=dev",
                "WEB_BASE=http://localhost",
                "REDIRECT_URI=http://localhost/auth/callback",
                "KC_PUBLIC_BASE_URL=http://localhost/id",
                "KC_BASE=http://localhost/id",
                "KC_BASE_URL=http://localhost/id",
                "SESSIONS_BACKEND=memory",
                "AUTO_CREATE_STORAGE_BUCKETS=true",
                "REQUIRE_STORAGE_VERIFY=false",
                "ENABLE_DEV_UPLOAD_STUB=true",
                "ENABLE_STORAGE_UPLOAD_PROXY=true",
                "H5P_REVIEW_TOKEN_SECRET=real-h5p-secret",
                "APP_CSRF_TOKEN_SECRET=CHANGE_ME_DEV",
            ]
        )
        + "\n"
    )

    mod = importlib.import_module("scripts.sync_prod_env")
    monkeypatch.setattr(mod, "ENV_PATH", envfile)
    monkeypatch.setattr(mod, "_run", lambda *_args, **_kwargs: None)

    mod.main()

    csrf_secret = _read_env_value(envfile, "APP_CSRF_TOKEN_SECRET")
    assert csrf_secret
    assert not csrf_secret.upper().startswith("CHANGE_ME")
