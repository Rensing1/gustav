"""
Keycloak theme presence and minimal contract tests (RED phase).

Why:
    We rely on a lightweight, branded Keycloak login/register/reset UI.
    To keep regressions low, assert that required templates, i18n overrides
    and CSS hooks exist in the repo.

Scope:
    - Existence of FTL templates: login, register, reset password
    - German message bundle with key overrides
    - CSS contains expected layout class hooks used in templates
"""

from pathlib import Path


THEME_ROOT = Path("keycloak/themes/gustav/login")


def test_theme_templates_present():
    """Templates may be stored at theme root or under a templates/ subdir.

    Accept either layout to avoid coupling tests to folder structure.
    """
    root_files = {
        "login.ftl": (THEME_ROOT / "login.ftl").exists(),
        "register.ftl": (THEME_ROOT / "register.ftl").exists(),
        "login-reset-password.ftl": (THEME_ROOT / "login-reset-password.ftl").exists(),
    }
    tmpl_dir = THEME_ROOT / "templates"
    dir_files = {
        "login.ftl": (tmpl_dir / "login.ftl").exists(),
        "register.ftl": (tmpl_dir / "register.ftl").exists(),
        "login-reset-password.ftl": (tmpl_dir / "login-reset-password.ftl").exists(),
    }
    for name in ["login.ftl", "register.ftl", "login-reset-password.ftl"]:
        assert root_files[name] or dir_files[name], f"{name} missing"


def test_theme_messages_de_present_and_has_keys():
    msgs = THEME_ROOT / "messages" / "messages_de.properties"
    assert msgs.exists(), "messages_de.properties missing"
    content = msgs.read_text(encoding="utf-8")
    # Minimal keys we rely on for German UI
    for key in [
        "doLogIn=",
        "doRegister=",
        "doForgotPassword=",
        "usernameOrEmail=",
        "password=",
    ]:
        assert key in content, f"Missing i18n key: {key}"


def test_theme_css_contains_component_hooks():
    css = THEME_ROOT / "resources" / "css" / "gustav.css"
    assert css.exists(), "gustav.css missing"
    text = css.read_text(encoding="utf-8")
    # Expected class hooks used by our FTL templates for compact layout
    for cls in [
        ".kc-card",
        ".kc-title",
        ".kc-form",
        ".kc-label",
        ".kc-input",
        ".kc-submit",
        ".kc-message",
        ".kc-links",
    ]:
        assert cls in text, f"Missing CSS hook: {cls}"
