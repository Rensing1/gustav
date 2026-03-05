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
    We ship both Keycloak names (login-update-password.ftl is the default; update-password.ftl is an alias),
    so both files must exist either at root or under templates/.
    """
    root_files = {
        "login.ftl": (THEME_ROOT / "login.ftl").exists(),
        "register.ftl": (THEME_ROOT / "register.ftl").exists(),
        "login-reset-password.ftl": (THEME_ROOT / "login-reset-password.ftl").exists(),
        "update-password.ftl": (THEME_ROOT / "update-password.ftl").exists(),
        "login-update-password.ftl": (THEME_ROOT / "login-update-password.ftl").exists(),
        "login-verify-email.ftl": (THEME_ROOT / "login-verify-email.ftl").exists(),
        "info.ftl": (THEME_ROOT / "info.ftl").exists(),
        "error.ftl": (THEME_ROOT / "error.ftl").exists(),
        "login-page-expired.ftl": (THEME_ROOT / "login-page-expired.ftl").exists(),
    }
    tmpl_dir = THEME_ROOT / "templates"
    dir_files = {
        "login.ftl": (tmpl_dir / "login.ftl").exists(),
        "register.ftl": (tmpl_dir / "register.ftl").exists(),
        "login-reset-password.ftl": (tmpl_dir / "login-reset-password.ftl").exists(),
        "update-password.ftl": (tmpl_dir / "update-password.ftl").exists(),
        "login-update-password.ftl": (tmpl_dir / "login-update-password.ftl").exists(),
        "login-verify-email.ftl": (tmpl_dir / "login-verify-email.ftl").exists(),
        "info.ftl": (tmpl_dir / "info.ftl").exists(),
        "error.ftl": (tmpl_dir / "error.ftl").exists(),
        "login-page-expired.ftl": (tmpl_dir / "login-page-expired.ftl").exists(),
    }
    for name in [
        "login.ftl",
        "register.ftl",
        "login-reset-password.ftl",
        # Keycloak default uses login-update-password.ftl; allow update-password.ftl alias.
        "update-password.ftl",
        "login-update-password.ftl",
        "login-verify-email.ftl",
        "info.ftl",
        "error.ftl",
        "login-page-expired.ftl",
    ]:
        assert root_files[name] or dir_files[name], f"{name} missing"


def _resolve_login_template(name: str) -> Path:
    root_tpl = THEME_ROOT / name
    dir_tpl = THEME_ROOT / "templates" / name
    tpl = root_tpl if root_tpl.exists() else dir_tpl
    assert tpl.exists(), f"{name} missing"
    return tpl


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
    assert "checked" not in text, "rememberMe checkbox must not be preselected by default"


def test_update_password_templates_use_login_css_hooks():
    """Update-password templates should reuse the login layout hooks for consistency."""
    for name in ["update-password.ftl", "login-update-password.ftl"]:
        tpl = _resolve_login_template(name)
        text = tpl.read_text(encoding="utf-8")
        for cls in [
            "kc-card",
            "kc-title",
            "kc-form",
            "kc-label",
            "kc-input",
            "kc-submit",
            "kc-message",
        ]:
            assert cls in text, f"{name} should contain CSS hook {cls}"


def test_update_password_templates_use_keycloak_field_names():
    """Update-password form must use Keycloak's expected field names and autocomplete hints."""
    for name in ["update-password.ftl", "login-update-password.ftl"]:
        tpl = _resolve_login_template(name)
        text = tpl.read_text(encoding="utf-8")
        assert 'name="password-new"' in text, f"{name} must post password-new"
        assert 'name="password-confirm"' in text, f"{name} must post password-confirm"
        assert 'autocomplete="new-password"' in text, f"{name} should set autocomplete=new-password"


def test_verify_email_template_uses_gustav_layout_hooks():
    """Verify-email page should keep the same compact GUSTAV layout."""
    tpl = _resolve_login_template("login-verify-email.ftl")
    text = tpl.read_text(encoding="utf-8")
    for marker in [
        'class="kc-gustav"',
        'class="kc-card"',
        "app-gustav-base.css",
        "gustav.css",
    ]:
        assert marker in text, f"login-verify-email.ftl should include {marker}"


def test_info_template_uses_gustav_layout_hooks():
    """Info page should keep the same compact GUSTAV layout."""
    tpl = _resolve_login_template("info.ftl")
    text = tpl.read_text(encoding="utf-8")
    for marker in [
        'class="kc-gustav"',
        'class="kc-card"',
        "app-gustav-base.css",
        "gustav.css",
    ]:
        assert marker in text, f"info.ftl should include {marker}"


def test_error_templates_use_gustav_layout_and_deemphasized_locale_links():
    """Error pages should be branded and use shared helper macros for footer actions."""
    for name in ["error.ftl", "login-page-expired.ftl"]:
        tpl = _resolve_login_template(name)
        text = tpl.read_text(encoding="utf-8")
        for marker in [
            'class="kc-gustav"',
            'class="kc-card"',
            "app-gustav-base.css",
            "gustav.css",
            '<#import "_gustav_error_components.ftl" as gustav_error>',
            "<@gustav_error.render_recovery_links",
            "<@gustav_error.render_locale_links",
        ]:
            assert marker in text, f"{name} should include {marker}"
        assert 'id="kc-locale"' not in text, f"{name} should not render a dominant locale dropdown"


def test_error_templates_expose_context_specific_guidance_and_i18n_keys():
    """Error pages should use deterministic, context-specific guidance and CTA keys."""
    helper_text = (THEME_ROOT / "_gustav_error_components.ftl").read_text(encoding="utf-8")
    expected = {
        "error.ftl": [
            "gustavBackToApp",
            "gustavTryLoginAgain",
            "gustavAuthErrorTitle",
            "gustavAuthErrorGeneralHint",
        ],
        "login-page-expired.ftl": [
            "gustavBackToApp",
            "gustavTryLoginAgain",
            "gustavAuthExpiredTitle",
            "gustavAuthErrorTokenHint",
        ],
    }
    for name, keys in expected.items():
        tpl = _resolve_login_template(name)
        text = tpl.read_text(encoding="utf-8")
        combined = text + "\n" + helper_text
        for key in keys:
            assert key in combined, f"{name} should reference i18n key {key}"
        assert "pageRedirectUri" in text or "client.baseUrl" in text, f"{name} should include app-link fallback"
        # Avoid text-parsing heuristics that are brittle across locale/version changes.
        assert "raw_summary" not in text, f"{name} should not parse message summary text"
        assert '?contains("cookie")' not in text, f"{name} should not infer state from text contains()"
        assert '?contains("token")' not in text, f"{name} should not infer state from text contains()"


def test_error_page_i18n_keys_exist_in_de_and_en_bundles():
    """Both language bundles should define error-page keys to avoid raw key output."""
    de = (THEME_ROOT / "messages" / "messages_de.properties").read_text(encoding="utf-8")
    en = (THEME_ROOT / "messages" / "messages_en.properties").read_text(encoding="utf-8")
    for key in [
        "gustavAuthErrorTitle=",
        "gustavAuthExpiredTitle=",
        "gustavAuthErrorGeneralHint=",
        "gustavAuthErrorCookieHint=",
        "gustavAuthErrorTokenHint=",
        "gustavBackToApp=",
        "gustavTryLoginAgain=",
        "gustavLanguageLabel=",
    ]:
        assert key in de, f"messages_de.properties missing {key}"
        assert key in en, f"messages_en.properties missing {key}"


def test_error_template_helpers_render_footer_links_and_localized_language_label():
    """Shared helper template should own footer link markup and localized language label."""
    helper = THEME_ROOT / "_gustav_error_components.ftl"
    assert helper.exists(), "_gustav_error_components.ftl missing"
    text = helper.read_text(encoding="utf-8")
    for marker in [
        'class="kc-links"',
        'class="kc-locale-links"',
        'msg("gustavLanguageLabel")',
    ]:
        assert marker in text, f"_gustav_error_components.ftl should include {marker}"
    assert 'id="kc-locale"' not in text, "helper should not render a dominant locale dropdown"


def test_error_template_helpers_resolve_primary_app_link_and_guard_idp_account_targets():
    """Helper must centralize app-link selection and reject IdP account URLs as primary CTA."""
    helper = THEME_ROOT / "_gustav_error_components.ftl"
    text = helper.read_text(encoding="utf-8")
    for marker in [
        "<#function resolve_primary_app_link",
        "<#function is_idp_account_link",
        "/realms/",
        "/account/",
    ]:
        assert marker in text, f"_gustav_error_components.ftl should include {marker}"


def test_error_template_helper_enforces_scheme_and_host_allowlist_contract():
    """Template resolver should reject unsafe schemes and external absolute hosts."""
    helper = THEME_ROOT / "_gustav_error_components.ftl"
    text = helper.read_text(encoding="utf-8")
    for marker in [
        "<#function is_allowed_app_link",
        'normalized_link?starts_with("javascript:")',
        'normalized_link?starts_with("data:")',
        'normalized_link?starts_with("vbscript:")',
        'normalized_link?starts_with("//")',
        'normalized_link?starts_with("http://")',
        'normalized_link?starts_with("https://")',
        'normalized_link?starts_with("/")',
        "normalized_link == trusted_base_url",
        'trusted_base_url + "/"',
        'trusted_base_url + "?"',
        'trusted_base_url + "#"',
    ]:
        assert marker in text, f"_gustav_error_components.ftl should include {marker}"


def test_error_template_helper_checks_protocol_relative_before_relative_paths():
    """Protocol-relative URLs must be blocked before generic relative-path acceptance."""
    helper = THEME_ROOT / "_gustav_error_components.ftl"
    text = helper.read_text(encoding="utf-8")
    protocol_relative = 'normalized_link?starts_with("//")'
    relative = 'normalized_link?starts_with("/")'
    assert protocol_relative in text, "helper should explicitly guard protocol-relative URLs"
    assert relative in text, "helper should allow regular relative app paths"
    assert text.index(protocol_relative) < text.index(relative), (
        "protocol-relative guard must run before relative-path allow branch"
    )


def test_error_template_helper_resolver_prefers_page_redirect_then_client_base():
    """Resolver must keep deterministic priority and guard both branches against IdP account targets."""
    helper = THEME_ROOT / "_gustav_error_components.ftl"
    text = helper.read_text(encoding="utf-8")
    page_redirect_branch = (
        "<#if pageRedirectUri?has_content && is_allowed_app_link(pageRedirectUri, clientBaseUrl)"
        " && !is_idp_account_link(pageRedirectUri)>"
    )
    client_base_branch = (
        "<#if clientBaseUrl?has_content && is_allowed_app_link(clientBaseUrl, clientBaseUrl)"
        " && !is_idp_account_link(clientBaseUrl)>"
    )
    fallback_return = '<#return "">'
    for marker in [page_redirect_branch, client_base_branch, fallback_return]:
        assert marker in text, f"_gustav_error_components.ftl should include {marker}"
    assert text.index(page_redirect_branch) < text.index(client_base_branch) < text.index(fallback_return), (
        "resolver order must be pageRedirectUri, then clientBaseUrl, then empty fallback"
    )


def test_error_template_helper_guards_idp_account_target_edge_shapes():
    """IdP account guard should cover /account with slash, query and fragment variants."""
    helper = THEME_ROOT / "_gustav_error_components.ftl"
    text = helper.read_text(encoding="utf-8")
    for marker in [
        '?ends_with("/account")',
        "/account?",
        "/account#",
    ]:
        assert marker in text, f"_gustav_error_components.ftl should guard edge shape {marker}"


def test_error_templates_use_shared_primary_app_link_resolver():
    """Error templates should use shared resolver instead of duplicated inline fallback chains."""
    for name in ["error.ftl", "login-page-expired.ftl"]:
        tpl = _resolve_login_template(name)
        text = tpl.read_text(encoding="utf-8")
        assert "resolve_primary_app_link" in text, f"{name} should use shared app-link resolver"
        assert "<#if pageRedirectUri?has_content>" not in text, f"{name} should not duplicate inline app-link selection"


def test_info_template_uses_shared_primary_app_link_resolver_and_keeps_action_fallback():
    """Info template should use shared app-link resolver and keep actionUri recovery option."""
    tpl = _resolve_login_template("info.ftl")
    text = tpl.read_text(encoding="utf-8")
    assert '<#import "_gustav_error_components.ftl" as gustav_error>' in text
    assert "resolve_primary_app_link" in text, "info.ftl should use shared app-link resolver"
    assert "actionUri" in text, "info.ftl should keep actionUri fallback behavior"


def test_info_template_enforces_exclusive_link_priority():
    """Info template should render one primary CTA with required-action safety priority."""
    tpl = _resolve_login_template("info.ftl")
    text = tpl.read_text(encoding="utf-8")
    for marker in [
        "<#assign has_required_actions = requiredActions?? && requiredActions?size gt 0>",
        "<#if has_required_actions && actionUri?has_content>",
        "<#elseif app_link?has_content>",
        "<#elseif actionUri?has_content>",
        "<#elseif url.loginUrl?has_content>",
    ]:
        assert marker in text, f"info.ftl should include exclusive priority marker {marker}"
    assert (
        text.index("<#if has_required_actions && actionUri?has_content>")
        < text.index("<#elseif app_link?has_content>")
    ), "required-action branch must precede app-link branch"
    assert "has_link" not in text, "info.ftl should not rely on multi-link accumulator state"


def test_messages_en_present_and_has_email_label():
    """English message bundle should exist and use email-only label."""
    msgs = THEME_ROOT / "messages" / "messages_en.properties"
    assert msgs.exists(), "messages_en.properties missing"
    content = msgs.read_text(encoding="utf-8")
    # Ensure the login label prefers email-only wording
    assert "usernameOrEmail=Email address" in content
    # Remember-me label should be present so the checkbox is announced correctly
    assert "rememberMe=" in content, "Missing i18n key: rememberMe="
    # Password policy hint must exist to avoid rendering key names on the register page.
    assert "gustavPasswordPolicyHint=" in content, "Missing i18n key: gustavPasswordPolicyHint="


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


def test_register_policy_hint_does_not_contradict_realm_policy():
    """Hint text must not claim special characters are unnecessary."""
    disallowed_text = "Keine Sonderzeichen erforderlich"
    reg = THEME_ROOT / "register.ftl"
    reg_text = reg.read_text(encoding="utf-8")
    assert disallowed_text not in reg_text, "register.ftl fallback hint contradicts realm password policy"

    msgs = THEME_ROOT / "messages" / "messages_de.properties"
    msg_text = msgs.read_text(encoding="utf-8")
    assert disallowed_text not in msg_text, "German password policy hint contradicts realm password policy"


def test_email_templates_present_for_verification_and_reset():
    """Email theme must provide HTML templates for verification and reset flows."""
    html_root = EMAIL_THEME_ROOT / "html"
    verify_tpl = html_root / "email-verification.ftl"
    reset_tpl = html_root / "password-reset.ftl"

    assert verify_tpl.exists(), "email-verification.ftl missing for email verification flow"
    assert reset_tpl.exists(), "password-reset.ftl missing for password reset flow"


def test_email_templates_reference_support_contact():
    """Email templates should reference the centralized support contact."""
    html_root = EMAIL_THEME_ROOT / "html"
    theme_props = EMAIL_THEME_ROOT / "theme.properties"
    assert theme_props.exists(), "email theme.properties missing"
    props_text = theme_props.read_text(encoding="utf-8")
    assert "supportEmail=" in props_text, "theme.properties must define supportEmail"
    assert "support@school.example" not in props_text, "placeholder support email must not remain"

    for name in ["email-verification.ftl", "password-reset.ftl"]:
        tpl = html_root / name
        assert tpl.exists(), f"{name} missing"
        text = tpl.read_text(encoding="utf-8")
        assert "support@school.example" not in text, f"{name} must not contain placeholder support email"
        assert "${properties.supportEmail!" in text, f"{name} should read support contact from theme.properties"
