"""HTTP acceptance helpers must decode forms exactly as browsers do."""

import importlib

import pytest


@pytest.mark.parametrize("module_name,form_id,helper_name", [
    ("test_h5p_ajax_student_playback_e2e", "kc-form-login", "_parse_login_form"),
    ("test_h5p_assets_e2e", "kc-form-login", "_parse_login_form"),
    ("test_h5p_finisheddata_origin_null_e2e", "kc-form-login", "_parse_login_form"),
    ("test_h5p_import_errors_e2e", "kc-form-login", "_parse_login_form"),
    ("test_h5p_roundtrip_e2e", "kc-form-login", "_parse_login_form"),
    ("test_h5p_service_auth_e2e", "kc-form-login", "_parse_login_form"),
    ("test_identity_login_register_logout_e2e", "kc-form-login", "_parse_login_form"),
    ("test_identity_register_validation_e2e", "kc-register-form", "_parse_register_form"),
])
def test_http_form_helpers_decode_action_and_input_entities(module_name, form_id, helper_name):
    module = importlib.import_module(f"backend.tests_e2e.{module_name}")
    markup = f'<form id="{form_id}" action="/login?session_code=abc&amp;execution=step"><input name="state" value="a&amp;b"></form>'
    action, fields = getattr(module, helper_name)(markup, "https://id.localhost/realm")
    assert action == "https://id.localhost/login?session_code=abc&execution=step"
    assert fields["state"] == "a&b"
