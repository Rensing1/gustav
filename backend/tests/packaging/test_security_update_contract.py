"""Protect deployed security floors, including nested dependency copies."""
import json
from pathlib import Path

import pytest
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[3]


def test_compose_enables_the_single_internal_proxy_hop():
    source = (ROOT / 'docker-compose.yml').read_text()
    h5p = source.split('  h5p:\n', 1)[1].split('\n  learning-worker:', 1)[0]
    assert '- H5P_TRUST_PROXY=true' in h5p


@pytest.mark.parametrize('file,image,count', [
    ('Dockerfile', 'python:3.11.17-slim', 2),
    ('frontend/Dockerfile', 'node:24.22.1-alpine', 4),
    ('h5p-service/Dockerfile', 'node:24.22.1-alpine', 2),
    ('keycloak/Dockerfile', 'node:24.22.1-alpine', 1),
    ('keycloak/Dockerfile', 'quay.io/keycloak/keycloak:26.8.1', 1),
    ('reverse-proxy/Dockerfile', 'caddy:2.11.7-alpine', 1),
    ('docker-compose.yml', 'postgres:16.15', 1),
])
def test_images_have_reviewed_security_pins(file, image, count):
    assert (ROOT / file).read_text().count(image) == count


@pytest.mark.parametrize('workspace,floors', [
    ('frontend', {'markdown-it': '14.3.3', 'dompurify': '3.4.16', 'devalue': '5.9.3', 'source-map-js': '1.2.2'}),
    ('h5p-service', {'multer': '2.4.0', 'fast-uri': '3.1.8', 'follow-redirects': '1.16.1',
                     'image-size': '2.0.3', 'proxy-addr': '2.0.8', 'sanitize-html': '2.18.0', 'source-map-js': '1.2.2'}),
])
def test_all_resolved_copies_meet_security_floors(workspace, floors):
    packages = json.loads((ROOT / workspace / 'package-lock.json').read_text())['packages']
    for name, floor in floors.items():
        versions = [p['version'] for path, p in packages.items() if path.endswith('/node_modules/' + name) or path == 'node_modules/' + name]
        assert versions, name
        assert all(Version(v) >= Version(floor) for v in versions), (name, versions)


def test_provider_build_and_runtime_use_the_same_reviewed_version():
    source = (ROOT / 'keycloak/Dockerfile').read_text()
    assert source.count('KEYCLOAK_BCRYPT_VERSION=1.7.0') == 2
    assert 'test jar -Pdependency.keycloak.version=26.8.1' in source


def test_runtime_replaces_unmaintained_crypto_and_cache_packages():
    for name in ('backend/web/requirements.lock', 'backend/requirements-harness.lock'):
        source = (ROOT / name).read_text().lower()
        for forbidden in ('python-jose==', 'ecdsa==', '\ndiskcache=='):
            assert forbidden not in source
        assert 'pyjwt==2.15.1' in source
        assert 'diskcache-community==5.8.1' in source
        assert 'dspy==3.4.1+gustav.1' in source
