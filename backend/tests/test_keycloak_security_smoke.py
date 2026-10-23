"""Opt-in image tests: no existing container, database, realm or account is used."""
import json
import os
import secrets
import shutil
import socket
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import pytest
import requests

pytestmark = pytest.mark.skipif(os.getenv('RUN_KEYCLOAK_SECURITY_SMOKE') != '1', reason='run make test-keycloak-security-smoke')
ROOT = Path(__file__).resolve().parents[2]
PASSWORD = 'synthetic-bcrypt-password'
BCRYPT_HASH = '$2b$12$h5NodZASQHIrtcTmezj7iOktUuOAONxVuHGRnyprRIf17SuCKvYj6'


def compose_keycloak_environment(tmp_path, values):
    """Render the real Compose contract using only synthetic ENV inputs.

    No daemon or existing realm is changed. Disable service env_file loading so
    unrelated local secrets cannot enter the captured Compose output.
    """
    env_file = tmp_path / 'synthetic.env'
    env_file.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
    result = subprocess.run(
        ['docker', 'compose', '--env-file', str(env_file), '-f', str(ROOT / 'docker-compose.yml'),
         'config', '--no-env-resolution', '--format', 'json'],
        cwd=ROOT, env={'PATH': os.environ['PATH'], 'HOME': os.environ['HOME']},
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)['services']['keycloak']['environment']


@pytest.mark.parametrize('values,username,password', [
    ({}, 'admin', 'admin'),
    ({'KEYCLOAK_ADMIN': 'legacy-admin', 'KEYCLOAK_ADMIN_PASSWORD': 'synthetic-legacy'}, 'legacy-admin', 'synthetic-legacy'),
    ({'KC_BOOTSTRAP_ADMIN_USERNAME': 'new-admin', 'KC_BOOTSTRAP_ADMIN_PASSWORD': 'synthetic-new'}, 'new-admin', 'synthetic-new'),
    ({'KEYCLOAK_ADMIN': 'legacy-admin', 'KEYCLOAK_ADMIN_PASSWORD': 'synthetic-legacy',
      'KC_BOOTSTRAP_ADMIN_USERNAME': 'new-admin', 'KC_BOOTSTRAP_ADMIN_PASSWORD': 'synthetic-new'}, 'new-admin', 'synthetic-new'),
    ({'KEYCLOAK_ADMIN': 'legacy-admin', 'KEYCLOAK_ADMIN_PASSWORD': 'synthetic-legacy',
      'KC_BOOTSTRAP_ADMIN_USERNAME': '', 'KC_BOOTSTRAP_ADMIN_PASSWORD': ''}, 'legacy-admin', 'synthetic-legacy'),
])
def test_compose_bootstrap_interpolation(tmp_path, values, username, password):
    environment = compose_keycloak_environment(tmp_path, values)
    assert environment['KC_BOOTSTRAP_ADMIN_USERNAME'] == username
    assert environment['KC_BOOTSTRAP_ADMIN_PASSWORD'] == password
    assert 'KEYCLOAK_ADMIN' not in environment
    assert 'KEYCLOAK_ADMIN_PASSWORD' not in environment


@pytest.mark.parametrize('values,origin', [
    ({}, 'https://app.localhost'),
    ({'WEB_BASE': 'https://school.example'}, 'https://school.example'),
    ({'ORIGIN': 'https://legacy.example'}, 'https://legacy.example'),
    ({'ORIGIN': 'https://legacy.example', 'WEB_BASE': 'https://school.example'}, 'https://legacy.example'),
    ({'ORIGIN': '', 'WEB_BASE': 'https://school.example'}, 'https://school.example'),
    ({'ORIGIN': '', 'WEB_BASE': ''}, 'https://app.localhost'),
])
def test_compose_preserves_the_theme_recovery_origin(tmp_path, values, origin):
    """Keep existing recovery origins while excluding unrelated app secrets."""
    environment = compose_keycloak_environment(tmp_path, {
        **values, 'APP_CSRF_TOKEN_SECRET': 'synthetic-unrelated-secret',
    })
    assert environment['ORIGIN'] == origin
    assert 'APP_CSRF_TOKEN_SECRET' not in environment


def docker(*args, check=True):
    return subprocess.run(['docker', *args], cwd=ROOT, text=True, capture_output=True, check=check)


@pytest.fixture(scope='module')
def images(tmp_path_factory):
    suffix = uuid4().hex[:12]
    current = f'gustav-security-keycloak:{suffix}'
    previous = f'gustav-security-keycloak-old:{suffix}'
    # Frozen public baseline: also works in shallow CI checkouts after this PR merges.
    old_file = ROOT / 'backend/tests/fixtures/keycloak/26.7.3.Dockerfile'
    # Git does not record ordinary read bits: reproduce a restrictive deployment checkout.
    context = tmp_path_factory.mktemp('keycloak-restrictive-checkout')
    shutil.copytree(ROOT / 'keycloak', context / 'keycloak')
    shutil.copytree(ROOT / 'frontend/src/lib/styles', context / 'frontend/src/lib/styles')
    for name in ('package.json', 'package-lock.json'):
        shutil.copy2(ROOT / 'frontend' / name, context / 'frontend' / name)
    for name in ('register.ftl', 'logout-confirm.ftl'):
        (context / 'keycloak/themes/gustav/login' / name).chmod(0o600)
    for name in ('auth-theme.css', 'theme-tokens.css'):
        (context / 'frontend/src/lib/styles' / name).chmod(0o600)
    # The upgrade starts from a working old image, regardless of this checkout's modes.
    baseline = tmp_path_factory.mktemp('keycloak-readable-baseline')
    shutil.copytree(context, baseline, dirs_exist_ok=True)
    shutil.copyfile(old_file, baseline / 'keycloak/Dockerfile')
    for path in baseline.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    try:
        docker('build', '-f', str(context / 'keycloak/Dockerfile'), '-t', current, str(context))
        docker('build', '-f', str(baseline / 'keycloak/Dockerfile'), '-t', previous, str(baseline))
        yield previous, current
    finally:
        docker('image', 'rm', current, previous, check=False)


def test_all_theme_files_are_readable_by_the_keycloak_runtime_user(images):
    """Check the actual image as UID 1000/GID 0, including nested CSS and fonts."""
    result = docker('run', '--rm', '--user', '1000:0', '--entrypoint', '/bin/bash', images[1], '-ec', '''
        test "$UID" = 1000
        shopt -s globstar dotglob nullglob
        paths=(/opt/keycloak/themes/gustav/**)
        test "${#paths[@]}" -gt 0
        failed=0
        for path in "${paths[@]}"; do
            if ! test -r "$path" || { test -d "$path" && ! test -x "$path"; }; then
                echo "Unreadable theme path: $path" >&2
                failed=1
            fi
        done
        exit "$failed"
    ''', check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('upgrade', [False, True], ids=['empty-postgres', 'schema-upgrade'])
def test_discovery_bcrypt_and_schema_compatibility(images, upgrade, tmp_path):
    """Exercise real isolated images and DB migration without touching the stack.

    Only the synthetic master admin may inspect SPI registration or import the
    fixture realm. Preserve bcrypt as the realm hash policy so a successful old
    login cannot silently turn the upgrade check into an Argon2-only test.
    """
    suffix = uuid4().hex[:12]
    network, database, identity = (f'gustav-security-{part}-{suffix}' for part in ('net', 'db', 'id'))
    password = secrets.token_urlsafe(24)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'https://127.0.0.1:{port}'
    app_origin = 'https://school.example'
    certificate, private_key = tmp_path / 'tls.crt', tmp_path / 'tls.key'
    subprocess.run([
        'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
        '-keyout', str(private_key), '-out', str(certificate),
    ], capture_output=True, check=True)
    # This short-lived synthetic key is mounted read-only for Keycloak's non-root user.
    private_key.chmod(0o644)
    client = requests.Session()
    client.verify = str(certificate)

    def start(image, *, old=False, bootstrap_username='synthetic-admin', bootstrap_password=None):
        bootstrap_password = bootstrap_password or password
        if old:
            bootstrap_env = {'KEYCLOAK_ADMIN': bootstrap_username, 'KEYCLOAK_ADMIN_PASSWORD': bootstrap_password}
        else:
            environment = compose_keycloak_environment(tmp_path, {
                'KC_BOOTSTRAP_ADMIN_USERNAME': bootstrap_username, 'KC_BOOTSTRAP_ADMIN_PASSWORD': bootstrap_password,
                'ORIGIN': app_origin, 'KC_PUBLIC_BASE_URL': base,
                'KC_DB_USERNAME': 'keycloak', 'KC_DB_PASSWORD': password,
            })
            # Exercise every explicit runtime setting; only the isolated DB host differs.
            bootstrap_env = {**environment, 'KC_DB_URL': f'jdbc:postgresql://{database}:5432/keycloak'}
        env_args = [arg for key, value in bootstrap_env.items() for arg in ('-e', f'{key}={value}')]
        docker('run', '-d', '--name', identity, '--network', network, '-p', f'127.0.0.1:{port}:8443',
               '-v', f'{certificate}:/opt/keycloak/conf/tls.crt:ro',
               '-v', f'{private_key}:/opt/keycloak/conf/tls.key:ro',
               *env_args,
               image, 'start', '--optimized', '--import-realm', f'--hostname={base}',
               '--https-certificate-file=/opt/keycloak/conf/tls.crt',
               '--https-certificate-key-file=/opt/keycloak/conf/tls.key',
               f'--db-url=jdbc:postgresql://{database}:5432/keycloak', '--db-username=keycloak', f'--db-password={password}')
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            try:
                if client.get(base+'/realms/master/.well-known/openid-configuration',timeout=2).status_code == 200:
                    if not old:
                        logs = docker('logs', identity)
                        assert 'The option `shouldAttachRoute` is deprecated' not in logs.stdout + logs.stderr
                        assert 'Environment variable KEYCLOAK_ADMIN' not in logs.stdout + logs.stderr
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        # Only synthetic configuration is used; include server diagnostics on failure.
        pytest.fail('Keycloak did not become ready: '+docker('logs',identity,check=False).stdout[-6000:])

    def admin_login(username='synthetic-admin', supplied=None):
        return client.post(base+'/realms/master/protocol/openid-connect/token', data={
            'grant_type':'password', 'client_id':'admin-cli', 'username':username, 'password':supplied or password,
        },timeout=10)

    def admin_headers():
        response = admin_login()
        response.raise_for_status()
        return {'Authorization':'Bearer '+response.json()['access_token']}

    def verify_internal_spi(version):
        response = client.get(base+'/admin/serverinfo', headers=admin_headers(), timeout=10)
        response.raise_for_status()
        info = response.json()
        assert info['systemInfo']['version'] == version
        hashing = info['providers']['password-hashing']
        assert hashing['internal'] is True
        assert 'bcrypt' in hashing['providers']
        provider_version = '1.6.0' if version == '26.7.3' else '1.7.0'
        docker('exec', identity, 'test', '-f', f'/opt/keycloak/providers/keycloak-bcrypt-{provider_version}.jar')

    def setup_realm():
        realm = {'realm':'security-test','enabled':True, 'loginTheme':'gustav',
                 'passwordPolicy':'hashAlgorithm(bcrypt) and hashIterations(12)', 'clients':[{
            'clientId':'security-client','publicClient':True,'directAccessGrantsEnabled':True,
        }], 'users':[{'username':'student','enabled':True,'emailVerified':True,
            'firstName':'Synthetic','lastName':'Student','email':'student@example.com',
            'credentials':[{'type':'password','algorithm':'bcrypt','hashIterations':-1,
                            'hashedSaltedValue':BCRYPT_HASH,'temporary':False}]}]}
        created = client.post(base+'/admin/realms', json=realm,
                                headers=admin_headers(),timeout=10)
        assert created.status_code == 201, created.status_code

    def verify():
        discovery = client.get(base+'/realms/security-test/.well-known/openid-configuration',timeout=10)
        assert discovery.status_code == 200
        configuration = discovery.json()
        assert configuration['issuer'] == base+'/realms/security-test'
        assert configuration['jwks_uri'].startswith(base+'/')
        jwks = client.get(configuration['jwks_uri'], timeout=10)
        assert jwks.status_code == 200
        assert jwks.json()['keys']
        for supplied, expected in [('incorrect-synthetic-password',400), (PASSWORD,200), ('incorrect-synthetic-password',400)]:
            response = client.post(configuration['token_endpoint'],data={
                'grant_type':'password','client_id':'security-client','username':'student','password':supplied,
            },timeout=10)
            assert response.status_code == expected, response.status_code
            if expected == 200:
                assert response.json().get('access_token')
            else:
                assert response.json().get('error') == 'invalid_grant'
        headers = admin_headers()
        users = client.get(base+'/admin/realms/security-test/users', params={'username':'student', 'exact':'true'},
                             headers=headers, timeout=10)
        users.raise_for_status()
        user_id = users.json()[0]['id']
        credentials = client.get(base+f'/admin/realms/security-test/users/{user_id}/credentials', headers=headers, timeout=10)
        credentials.raise_for_status()
        password_credentials = [entry for entry in credentials.json() if entry['type'] == 'password']
        assert len(password_credentials) == 1
        assert json.loads(password_credentials[0]['credentialData'])['algorithm'] == 'bcrypt'

    def verify_registration(version):
        """Follow the imported realm's own registration link without submitting mail."""
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.registration = []

            def handle_starttag(self, tag, attrs):
                href = dict(attrs).get('href', '')
                if tag == 'a' and urlsplit(href).path == '/realms/gustav/login-actions/registration':
                    self.registration.append(href)

        with requests.Session() as browser:
            browser.verify = str(certificate)
            login = browser.get(base+'/realms/gustav/protocol/openid-connect/auth', params={
                'client_id': 'gustav-web', 'response_type': 'code', 'scope': 'openid',
                'redirect_uri': 'https://app.localhost/auth/callback', 'state': 'synthetic-state',
                'nonce': 'synthetic-nonce', 'code_challenge_method': 'S256',
                'code_challenge': 'a'*43,
            }, timeout=10)
            assert login.status_code == 200
            links = Links()
            links.feed(login.text)
            assert len(links.registration) == 1
            registration_url = urljoin(login.url, links.registration[0])
            assert urlsplit(registration_url).netloc == urlsplit(base).netloc
            registration = browser.get(registration_url, timeout=10)
        logs = docker('logs', identity)
        diagnostics = (logs.stdout + logs.stderr).replace(password, '[synthetic-secret]')
        (tmp_path / f'keycloak-registration-{version}.log').write_text(diagnostics)
        assert registration.status_code == 200, diagnostics
        assert '<title>Registrieren - GUSTAV</title>' in registration.text
        for field in ('kc-register-form', 'display_name', 'email', 'password', 'password-confirm'):
            assert f'id="{field}"' in registration.text
        for error in ('Failed to process template', 'FreeMarkerException', 'MediaType not set', 'Uncaught server error', 'HTTP 500'):
            assert error not in diagnostics, diagnostics

    try:
        docker('network','create',network)
        docker('run','-d','--name',database,'--network',network,
               '-e',f'POSTGRES_PASSWORD={password}','-e','POSTGRES_USER=keycloak','-e','POSTGRES_DB=keycloak',
               '--tmpfs','/var/lib/postgresql/data','postgres:16.15')
        for _ in range(60):
            if docker('exec',database,'pg_isready','-U','keycloak',check=False).returncode == 0:
                break
            time.sleep(1)
        else:
            pytest.fail('Isolated PostgreSQL did not become ready')
        start(images[0] if upgrade else images[1], old=upgrade)
        verify_internal_spi('26.7.3' if upgrade else '26.8.1')
        setup_realm()
        verify()
        verify_registration('26.7.3' if upgrade else '26.8.1')
        if upgrade:
            docker('rm','-f',identity)
            # Bootstrap values must neither reset nor create admins in an existing master realm.
            replacement_password = secrets.token_urlsafe(24)
            start(images[1], bootstrap_username='replacement-admin', bootstrap_password=replacement_password)
            verify_internal_spi('26.8.1')
            assert admin_login('synthetic-admin', replacement_password).status_code == 400
            assert admin_login('replacement-admin', replacement_password).status_code == 400
            verify()
            verify_registration('26.8.1')
        # Render the real theme without visiting the synthetic external app origin.
        recovery = client.get(base+'/realms/security-test/login-actions/action-token', params={
            'key':'invalid', 'pageRedirectUri':'https://untrusted.example/',
        }, timeout=10)
        assert recovery.status_code == 400
        assert f'href="{app_origin}/auth/login"' in recovery.text
        assert f'href="{app_origin}/auth/forgot"' in recovery.text
        assert 'href="https://untrusted.example' not in recovery.text
    finally:
        client.close()
        docker('rm','-f',identity,database,check=False)
        docker('network','rm',network,check=False)
