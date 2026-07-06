"""
Contract tests for public H5P runtime assets.

Why:
    The browser must load the H5P webcomponents and shared theme CSS before the
    authenticated editor/player model endpoints can render any UI.

    These assets are static runtime files, not user data. If they accidentally
    move behind `requireAuth`, the editor shell appears but the actual H5P UI
    never upgrades or becomes visible.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_static_runtime_assets_are_registered_before_require_auth() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assets_path = repo_root / "h5p-service" / "lib" / "public_assets.mjs"
    src = server_path.read_text(encoding="utf-8")
    assets_src = assets_path.read_text(encoding="utf-8")

    require_auth_index = src.index("app.use(requireAuth);")
    public_assets_index = src.index("mountPublicStaticAssets(app);")

    assert public_assets_index < require_auth_index
    assert '"/webcomponents"' in assets_src
    assert '"/theme"' in assets_src
    assert '"/webcomponents/vendor"' in assets_src
    assert "maxAge: 0" in assets_src


def test_h5p_model_endpoints_remain_protected_after_public_assets() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    src = server_path.read_text(encoding="utf-8")

    require_auth_index = src.index("app.use(requireAuth);")
    auth_me_index = src.index('app.get("/auth/me"')
    editor_model_index = src.index('app.get("/editor/model"')
    player_model_index = src.index('app.get("/player/model"')

    assert require_auth_index < auth_me_index
    assert require_auth_index < editor_model_index
    assert require_auth_index < player_model_index
