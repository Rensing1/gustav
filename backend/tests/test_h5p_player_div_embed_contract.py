"""
Contract test: H5P player must prefer DIV embed (no internal iframe).

Why:
    GUSTAV embeds Lumi's `<h5p-player>` webcomponent inside the regular student UI.
    By default H5P content is often rendered in an internal iframe, which makes
    it very hard to apply the GUSTAV theme (design tokens do not automatically
    exist inside that iframe).

    Therefore we force the player model to advertise `embedTypes` including
    `div`, so the webcomponent will render H5P directly into the page DOM.

Note:
    This test does not execute the Node service. It guards the presence of the
    embed-type override in the shipped server code.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_player_model_forces_div_embed_type() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_path = repo_root / "h5p-service" / "server.mjs"
    assert server_path.is_file(), f"Missing H5P service file: {server_path}"

    js = server_path.read_text(encoding="utf-8")

    # We add a small helper and apply it to the /player/model output.
    assert "ensureDivEmbedTypes" in js
    assert "embedTypes: ensureDivEmbedTypes" in js

