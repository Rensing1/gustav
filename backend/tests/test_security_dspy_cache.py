"""Persistent AI cache data must never become executable Python instructions."""
import pickle
import sqlite3

import pytest
from diskcache_community import SafeDisk
from dspy.clients.cache import Cache
from dspy.clients.gustav_safe_disk import safe_disk
from litellm import ModelResponse


def make_cache(directory):
    return Cache(enable_disk_cache=True, enable_memory_cache=False,
                 disk_cache_dir=str(directory), disk_size_limit_bytes=1024*1024)


def response():
    return ModelResponse(choices=[{'message': {'role': 'assistant', 'content': 'synthetic feedback'}}],
                         usage={'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5})


def test_safe_disk_is_mandatory_and_reopens_without_legacy_files(tmp_path):
    legacy = tmp_path / 'cache.db'
    legacy.write_bytes(b'legacy cache must not be opened')
    first = make_cache(tmp_path)
    assert issubclass(safe_disk(), SafeDisk)
    first.put({'prompt': 'synthetic'}, response())
    first.disk_cache.close()
    second = make_cache(tmp_path)
    hit = second.get({'prompt': 'synthetic'})
    assert hit.choices[0].message.content == 'synthetic feedback'
    assert hit.cache_hit is True
    assert hit.usage == {}
    assert legacy.read_bytes() == b'legacy cache must not be opened'
    second.disk_cache.close()


def test_tampered_pickles_are_misses_without_execution(tmp_path):
    sentinel = tmp_path / 'executed'
    class Payload:
        def __reduce__(self):
            return eval, (f"__import__('pathlib').Path({str(sentinel)!r}).touch()",)
    cache = make_cache(tmp_path / 'cache')
    request = {'prompt': 'synthetic'}
    cache.put(request, response())
    key = cache.cache_key(request)
    changed = 0
    for database in (tmp_path / 'cache').rglob('cache.db'):
        with sqlite3.connect(database) as db:
            changed += db.execute('UPDATE Cache SET mode=4, value=?, filename=NULL WHERE key=?',
                                  (pickle.dumps(Payload()), key)).rowcount
    assert changed == 1
    assert cache.get(request) is None
    assert not sentinel.exists()
    cache.put(request, response())
    assert cache.get(request).choices[0].message.content == 'synthetic feedback'
    cache.disk_cache.close()


def test_arbitrary_classes_cannot_be_allowlisted(tmp_path):
    class Custom:
        pass
    with pytest.raises(ValueError):
        Cache(True, False, str(tmp_path), safe_types=[Custom])


def test_cache_persists_across_a_new_python_process(tmp_path):
    import os
    import subprocess
    import sys
    first = make_cache(tmp_path)
    first.put({'prompt': 'synthetic'}, response())
    first.disk_cache.close()
    code = '''
import sys
from dspy.clients.cache import Cache
cache = Cache(True, False, sys.argv[1])
hit = cache.get({'prompt': 'synthetic'})
assert hit.choices[0].message.content == 'synthetic feedback'
assert hit.cache_hit
cache.disk_cache.close()
'''
    subprocess.run([sys.executable, '-c', code, str(tmp_path)], check=True, timeout=20,
                   env={**os.environ, 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'})


def test_value_paths_cannot_escape_the_cache_directory(tmp_path):
    outside = tmp_path / 'outside'
    outside.write_bytes(b'must not read or delete')
    cache = make_cache(tmp_path / 'cache')
    request = {'prompt': 'synthetic'}
    cache.put(request, response())
    key = cache.cache_key(request)
    for database in (tmp_path / 'cache').rglob('cache.db'):
        with sqlite3.connect(database) as db:
            db.execute('UPDATE Cache SET mode=4, value=NULL, filename=? WHERE key=?', (str(outside), key))
    assert cache.get(request) is None
    assert outside.read_bytes() == b'must not read or delete'
    cache.disk_cache.close()
