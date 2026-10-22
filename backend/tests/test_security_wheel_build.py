"""A local distribution must be reproducible and must not conceal its origin."""
import io
import zipfile
from pathlib import Path

import pytest

from build_support.build_dspy_wheel import build


def test_builder_rejects_changed_upstream_before_patching():
    with pytest.raises(ValueError, match='SHA-256'):
        build(b'not the reviewed upstream wheel')


def test_local_version_requires_safe_cache_and_preserves_complete_dependencies():
    from importlib.metadata import distribution
    dist = distribution('dspy')
    assert dist.version == '3.4.1+gustav.1'
    assert 'diskcache-community==5.8.1' in dist.requires
    assert not any(requirement.split('>')[0].split('=')[0] == 'diskcache' for requirement in dist.requires)


def test_builder_is_byte_reproducible_with_no_absolute_paths():
    # The immutable source is downloaded by the build step, never supplied by users.
    source = Path('.tmp/upstream/dspy-3.4.1-py3-none-any.whl')
    if not source.exists():
        pytest.skip('source artifact is checked separately by make lock-python')
    first = build(source.read_bytes())
    assert first == build(source.read_bytes())
    with zipfile.ZipFile(io.BytesIO(first)) as wheel:
        assert all(not name.startswith('/') and '..' not in name.split('/') for name in wheel.namelist())
        assert b'Requires-Dist: diskcache-community==5.8.1' in wheel.read('dspy-3.4.1+gustav.1.dist-info/METADATA')
