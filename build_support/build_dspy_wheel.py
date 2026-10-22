"""Build the reviewed DSPy variant deterministically from a verified PyPI wheel.

The complete dependency graph is resolved normally. No installation removes
requirements after resolution. Zip timestamps, order and RECORD are stable so
runtime and harness locks can verify the same artifact in every environment.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

SOURCE_URL = 'https://files.pythonhosted.org/packages/ad/2f/656f16206c9ba4e359b639e2605cf196a4e5c678c6d9aed0fae537701ec2/dspy-3.4.1-py3-none-any.whl'
SOURCE_SHA256 = 'afda9e7f8b3d46be0829af19ac1153a6feaa6db5923f2b1011eef547fb15ce2d'
VERSION = '3.4.1+gustav.1'
PATCH_ROOT = Path(__file__).parent / 'dspy'


def build(source: bytes) -> bytes:
    """Reject unreviewed upstream bytes and return a reproducible patched wheel."""
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('DSPy upstream SHA-256 mismatch')
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        files = {name.replace('dspy-3.4.1.dist-info/', f'dspy-{VERSION}.dist-info/'): archive.read(name)
                 for name in archive.namelist() if not name.endswith('/')}
    for change in json.loads((PATCH_ROOT / 'replacements.json').read_text()):
        name, old, new, *expected = change
        text = files[name].decode()
        if text.count(old) != (expected[0] if expected else 1):
            raise ValueError(f'DSPy patch drift: {name}')
        files[name] = text.replace(old, new).encode()
    files['dspy/clients/gustav_safe_disk.py'] = (PATCH_ROOT / 'gustav_safe_disk.py').read_bytes()
    # Keep the existing import surface while removing its unsafe implementation.
    files['dspy/clients/disk_serialization.py'] = (
        '"""Compatibility names backed exclusively by the GUSTAV SafeDisk policy."""\n'
        'from pickle import UnpicklingError as DeserializationError\n'
        'from dspy.clients.gustav_safe_disk import safe_disk\n\n'
        'def restricted_disk(allowed=frozenset()):\n'
        '    if allowed:\n'
        '        raise ValueError("Custom cache classes are not allowed")\n'
        '    return safe_disk()\n'
    ).encode()
    metadata = f'dspy-{VERSION}.dist-info/METADATA'
    original = files[metadata].decode()
    if original.count('Requires-Dist: diskcache>=5.6.0') != 1:
        raise ValueError('Unexpected DSPy dependency metadata')
    files[metadata] = original.replace('Version: 3.4.1\n', f'Version: {VERSION}\n').replace(
        'Requires-Dist: diskcache>=5.6.0', 'Requires-Dist: diskcache-community==5.8.1').encode()
    record = f'dspy-{VERSION}.dist-info/RECORD'
    files.pop(record)
    manifest = io.StringIO(newline='')
    writer = csv.writer(manifest, lineterminator='\n')
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
        writer.writerow([name, f'sha256={digest}', len(data)])
    writer.writerow([record, '', ''])
    files[record] = manifest.getvalue().encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('.tmp/security-wheels'))
    args = parser.parse_args()
    if args.source:
        source = args.source.read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
            source = response.read()
    result = build(source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / f'dspy-{VERSION}-py3-none-any.whl'
    destination.write_bytes(result)
    print(f'{destination.name}: sha256:{hashlib.sha256(result).hexdigest()}')


if __name__ == '__main__':
    main()
