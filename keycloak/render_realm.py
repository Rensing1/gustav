"""
Render the public Keycloak realm template with deployment-specific registration domains.

Why:
    FastAPI, the SvelteKit BFF and the IdP must enforce the same self-registration
    domain policy. The public repo keeps a neutral placeholder domain in the
    template, while deployments derive the concrete regex from
    `ALLOWED_REGISTRATION_DOMAINS` during the Keycloak image build.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_ALLOWED_REGISTRATION_DOMAINS = "@school.example"
EMAIL_PATTERN_PLACEHOLDER = "__GUSTAV_ALLOWED_EMAIL_PATTERN__"


def parse_allowed_registration_domains(raw: str | None) -> tuple[str, ...]:
    """Normalize the env value into deterministic `@domain` entries.

    Security:
        Invalid entries fail the render step instead of silently drifting the
        Keycloak policy away from the app configuration.
    """
    normalized = str(raw or "").strip()
    if not normalized:
        return (DEFAULT_ALLOWED_REGISTRATION_DOMAINS,)

    domains: list[str] = []
    seen: set[str] = set()
    for part in normalized.split(","):
        value = part.strip().lower()
        if not value:
            continue
        if not value.startswith("@") or value.count("@") != 1 or value.endswith("@") or any(ch.isspace() for ch in value):
            raise ValueError(
                "ALLOWED_REGISTRATION_DOMAINS entries must look like '@school.example' and be comma-separated."
            )
        if value not in seen:
            seen.add(value)
            domains.append(value)

    if not domains:
        return (DEFAULT_ALLOWED_REGISTRATION_DOMAINS,)
    return tuple(domains)


def build_allowed_email_pattern(allowed_domains: tuple[str, ...]) -> str:
    """Create the Keycloak regex for the configured registration domains."""
    escaped_domains = [re.escape(domain[1:]) for domain in allowed_domains]
    return rf"^[^@\s]+@(?:{'|'.join(escaped_domains)})$"


def _load_realm_template(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registration_profile_config(data: dict) -> tuple[list[str], dict]:
    providers = data.get("components", {}).get("org.keycloak.userprofile.UserProfileProvider", [])
    if not providers:
        raise ValueError("declarative user profile provider missing in realm template")

    config_items = providers[0].get("config", {}).get("kc.user.profile.config", [])
    if not config_items:
        raise ValueError("kc.user.profile.config missing in realm template")

    profile = json.loads(config_items[0])
    return config_items, profile


def render_realm_template(raw_allowed_domains: str | None, template_path: Path = Path("keycloak/realm-gustav.json")) -> dict:
    """Return the rendered realm export as Python data."""
    data = _load_realm_template(template_path)
    config_items, profile = _registration_profile_config(data)

    email_attribute = next((item for item in profile.get("attributes", []) if item.get("name") == "email"), None)
    if email_attribute is None:
        raise ValueError("email attribute missing in realm template")

    pattern_validation = email_attribute.setdefault("validations", {}).setdefault("pattern", {})
    if pattern_validation.get("pattern") != EMAIL_PATTERN_PLACEHOLDER:
        raise ValueError("realm template no longer contains the expected email pattern placeholder")

    pattern_validation["pattern"] = build_allowed_email_pattern(parse_allowed_registration_domains(raw_allowed_domains))
    config_items[0] = json.dumps(profile, ensure_ascii=False)
    return data


def write_rendered_realm(template_path: Path, output_path: Path, raw_allowed_domains: str | None) -> None:
    """Render the realm template and write the result to disk."""
    rendered = render_realm_template(raw_allowed_domains, template_path=template_path)
    output_path.write_text(json.dumps(rendered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Keycloak realm template for the current deployment.")
    parser.add_argument("--input", dest="input_path", required=True, help="Path to the realm template JSON file.")
    parser.add_argument("--output", dest="output_path", required=True, help="Path for the rendered realm export.")
    parser.add_argument(
        "--allowed-registration-domains",
        dest="allowed_registration_domains",
        default="",
        help="Comma-separated allow-list such as '@school.example,@other.example'.",
    )
    args = parser.parse_args()

    write_rendered_realm(
        template_path=Path(args.input_path),
        output_path=Path(args.output_path),
        raw_allowed_domains=args.allowed_registration_domains,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
