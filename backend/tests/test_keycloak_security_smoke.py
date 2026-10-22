"""Opt-in image tests: no existing container, database, realm or account is used."""
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
import requests

pytestmark = pytest.mark.skipif(os.getenv('RUN_KEYCLOAK_SECURITY_SMOKE') != '1', reason='run make test-keycloak-security-smoke')
ROOT = Path(__file__).resolve().parents[2]
PASSWORD = 'synthetic-bcrypt-password'
BCRYPT_HASH = '$2b$12$h5NodZASQHIrtcTmezj7iOktUuOAONxVuHGRnyprRIf17SuCKvYj6'


def docker(*args, check=True):
    return subprocess.run(['docker', *args], cwd=ROOT, text=True, capture_output=True, check=check)


@pytest.fixture(scope='module')
def images():
    suffix = uuid4().hex[:12]
    current = f'gustav-security-keycloak:{suffix}'
    previous = f'gustav-security-keycloak-old:{suffix}'
    # Frozen public baseline: also works in shallow CI checkouts after this PR merges.
    old_file = ROOT / 'backend/tests/fixtures/keycloak/26.7.3.Dockerfile'
    try:
        docker('build', '-f', 'keycloak/Dockerfile', '-t', current, '.')
        docker('build', '-f', str(old_file), '-t', previous, '.')
        yield previous, current
    finally:
        docker('image', 'rm', current, previous, check=False)


@pytest.mark.parametrize('upgrade', [False, True], ids=['empty-postgres', 'schema-upgrade'])
def test_discovery_bcrypt_and_schema_compatibility(images, upgrade):
    suffix = uuid4().hex[:12]
    network, database, identity = (f'gustav-security-{part}-{suffix}' for part in ('net', 'db', 'id'))
    password = secrets.token_urlsafe(24)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'

    def start(image):
        docker('run', '-d', '--name', identity, '--network', network, '-p', f'127.0.0.1:{port}:8080',
               '-e', 'KC_BOOTSTRAP_ADMIN_USERNAME=synthetic-admin', '-e', f'KC_BOOTSTRAP_ADMIN_PASSWORD={password}',
               image, 'start', '--optimized', '--http-enabled=true', f'--hostname={base}',
               f'--db-url=jdbc:postgresql://{database}:5432/keycloak', '--db-username=keycloak', f'--db-password={password}')
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            try:
                if requests.get(base+'/realms/master/.well-known/openid-configuration',timeout=2).status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        # Only synthetic configuration is used; include server diagnostics on failure.
        pytest.fail('Keycloak did not become ready: '+docker('logs',identity,check=False).stdout[-6000:])

    def setup_realm():
        response = requests.post(base+'/realms/master/protocol/openid-connect/token', data={
            'grant_type':'password', 'client_id':'admin-cli', 'username':'synthetic-admin', 'password':password,
        },timeout=10)
        response.raise_for_status()
        realm = {'realm':'security-test','enabled':True,'clients':[{
            'clientId':'security-client','publicClient':True,'directAccessGrantsEnabled':True,
        }], 'users':[{'username':'student','enabled':True,'emailVerified':True,
            'firstName':'Synthetic','lastName':'Student','email':'student@example.com',
            'credentials':[{'type':'password','algorithm':'bcrypt','hashIterations':-1,
                            'hashedSaltedValue':BCRYPT_HASH,'temporary':False}]}]}
        created = requests.post(base+'/admin/realms', json=realm,
                                headers={'Authorization':'Bearer '+response.json()['access_token']},timeout=10)
        assert created.status_code == 201, created.status_code

    def verify():
        discovery = requests.get(base+'/realms/security-test/.well-known/openid-configuration',timeout=10)
        assert discovery.status_code == 200
        configuration = discovery.json()
        assert configuration['issuer'] == base+'/realms/security-test'
        assert configuration['jwks_uri'].startswith(base+'/')
        for supplied, expected in [(PASSWORD,200), ('incorrect-synthetic-password',400)]:
            response = requests.post(configuration['token_endpoint'],data={
                'grant_type':'password','client_id':'security-client','username':'student','password':supplied,
            },timeout=10)
            assert response.status_code == expected, response.status_code
            if expected == 200:
                assert response.json().get('access_token')
            else:
                assert response.json().get('error') == 'invalid_grant'

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
        start(images[0] if upgrade else images[1])
        setup_realm()
        verify()
        if upgrade:
            docker('rm','-f',identity)
            start(images[1])
            verify()
    finally:
        docker('rm','-f',identity,database,check=False)
        docker('network','rm',network,check=False)
