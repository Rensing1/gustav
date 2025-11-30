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
EMAIL_THEME_ROOT = Path("keycloak/themes/gustav/email")


def test_theme_templates_present():
    """Templates may be stored at theme root or under a templates/ subdir.

    Accept either layout to avoid coupling tests to folder structure.
    """
    root_files = {
        "login.ftl": (THEME_ROOT / "login.ftl").exists(),
        "register.ftl": (THEME_ROOT / "register.ftl").exists(),
        "login-reset-password.ftl": (THEME_ROOT / "login-reset-password.ftl").exists(),
        "update-password.ftl": (THEME_ROOT / "update-password.ftl").exists(),
        "login-update-password.ftl": (THEME_ROOT / "login-update-password.ftl").exists(),
    }
    tmpl_dir = THEME_ROOT / "templates"
    dir_files = {
        "login.ftl": (tmpl_dir / "login.ftl").exists(),
        "register.ftl": (tmpl_dir / "register.ftl").exists(),
        "login-reset-password.ftl": (tmpl_dir / "login-reset-password.ftl").exists(),
        "update-password.ftl": (tmpl_dir / "update-password.ftl").exists(),
        "login-update-password.ftl": (tmpl_dir / "login-update-password.ftl").exists(),
    }
    for name in [
        "login.ftl",
        "register.ftl",
        "login-reset-password.ftl",
        # Keycloak default uses login-update-password.ftl; allow update-password.ftl alias.
        "update-password.ftl",
        "login-update-password.ftl",
    ]:
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
        "rememberMe=",
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


def test_login_username_input_is_email():
    """Login template should use an email input for username field (accessibility/UX)."""
    tpl = (THEME_ROOT / "login.ftl")
    assert tpl.exists(), "login.ftl missing"
    text = tpl.read_text(encoding="utf-8")
    assert 'id="username"' in text, "username input missing"
    assert 'type="email"' in text, "username input should be type=email"
    assert 'autocomplete="email"' in text, "username input should have autocomplete=email"


def test_login_has_conditional_remember_me_checkbox():
    """Login template should support Keycloak's remember-me feature in a minimal way.

    We expect a conditional block guarded by realm.rememberMe and a semantic checkbox
    with the standard rememberMe name so that IdP session lifetimes can be extended.
    """
    tpl = (THEME_ROOT / "login.ftl")
    assert tpl.exists(), "login.ftl missing"
    text = tpl.read_text(encoding="utf-8")
    assert "realm.rememberMe" in text, "rememberMe block should be conditional on realm.rememberMe"
    assert 'name="rememberMe"' in text, "rememberMe checkbox name must be rememberMe"
    assert 'type="checkbox"' in text, "rememberMe control must be a checkbox input"


def test_messages_en_present_and_has_email_label():
    """English message bundle should exist and use email-only label."""
    msgs = THEME_ROOT / "messages" / "messages_en.properties"
    assert msgs.exists(), "messages_en.properties missing"
    content = msgs.read_text(encoding="utf-8")
    # Ensure the login label prefers email-only wording
    assert "usernameOrEmail=Email address" in content
    # Remember-me label should be present so the checkbox is announced correctly
    assert "rememberMe=" in content, "Missing i18n key: rememberMe="


def test_register_uses_display_name_only():
    """Register template should prefer a single display name over first/last name fields."""
    reg = THEME_ROOT / "register.ftl"
    assert reg.exists(), "register.ftl missing"
    text = reg.read_text(encoding="utf-8")
    # Check presence of display name field by id and attribute mapping
    assert 'id="display_name"' in text or 'name="user.attributes.display_name"' in text, "display name field missing"
    assert 'name="user.attributes.display_name"' in text, "display name attribute missing"
    # Ensure first/last name fields are not present anymore
    assert 'id="firstName"' not in text, "firstName field should be removed"
    assert 'id="lastName"' not in text, "lastName field should be removed"
    # Ensure username field is not rendered when email is the username
    assert 'id="username"' not in text, "username field should be removed"


def test_register_display_name_required_and_styled():
    reg = THEME_ROOT / "register.ftl"
    text = reg.read_text(encoding="utf-8")
    # Label uses same kc-label class and msg key
    assert 'class="kc-label"' in text and 'for="display_name"' in text
    # Input uses kc-input and is required
    assert 'id="display_name"' in text and 'class="kc-input"' in text and 'required' in text


def test_email_templates_present_for_verification_and_reset():
    """Email theme must provide HTML templates for verification and reset flows."""
    html_root = EMAIL_THEME_ROOT / "html"
    verify_tpl = html_root / "email-verification.ftl"
    reset_tpl = html_root / "password-reset.ftl"

    assert verify_tpl.exists(), "email-verification.ftl missing for email verification flow"
    assert reset_tpl.exists(), "password-reset.ftl missing for password reset flow"


def test_email_templates_reference_support_contact():
    """Email templates should mention the support address in the footer."""
    html_root = EMAIL_THEME_ROOT / "html"
    support_email = "support@school.example"

    for name in ["email-verification.ftl", "password-reset.ftl"]:
        tpl = html_root / name
        assert tpl.exists(), f"{name} missing"
        text = tpl.read_text(encoding="utf-8")
        assert support_email in text, f"{name} should include support email {support_email}"
