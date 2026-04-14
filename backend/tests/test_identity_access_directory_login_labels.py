"""
Identity Directory — login-label resolvers expose email localparts.
"""
from __future__ import annotations

import threading
import types
import time
import pytest


def _kc_token_stub(self) -> str:  # type: ignore[override]
    return "dummy-token"


class _Resp:
    def __init__(self, status: int, data):
        self.status_code = status
        self._data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def test_resolve_student_login_labels_prefers_email_localpart(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        if "/roles/student/users" in str(url):
            return _Resp(
                200,
                [
                    {"id": "sub-a", "email": "max.mustermann@example.test", "username": "max.mustermann@example.test"},
                    {"id": "sub-b", "email": "", "username": "legacy-email:anna.von.beispiel@example.test"},
                ],
            )
        if "/roles/default-roles-gustav/users" in str(url):
            return _Resp(200, [])
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.resolve_student_login_labels(["sub-a", "sub-b", "sub-c"])
    assert out == {
        "sub-a": "max.mustermann",
        "sub-b": "anna.von.beispiel",
        "sub-c": "Unbekannt",
    }
    assert any("/roles/student/users" in url for url in called_urls)
    assert not any("/users/sub-a" in url or "/users/sub-b" in url for url in called_urls)


def test_resolve_student_login_labels_retries_with_admin_fallback_token(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    monkeypatch.setattr(dir._KC, "token_admin_fallback", lambda self: "admin-token")

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        auth = str((headers or {}).get("Authorization", ""))
        if "/roles/student/users" in str(url) and "dummy-token" in auth:
            return _Resp(403, {"error": "forbidden"})
        if "/roles/student/users" in str(url):
            return _Resp(
                200,
                [
                    {"id": "sub-a", "email": "eva.example@example.test", "username": "eva.example@example.test"},
                ],
            )
        if "/roles/default-roles-gustav/users" in str(url):
            return _Resp(200, [])
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.resolve_student_login_labels(["sub-a", "sub-b"])
    assert out == {"sub-a": "eva.example", "sub-b": "Unbekannt"}


def test_resolve_student_login_labels_by_sub_prefers_direct_user_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        if str(url).endswith("/users/sub-a"):
            return _Resp(
                200,
                {"id": "sub-a", "email": "alice.example@example.test", "username": "alice.example@example.test"},
            )
        if str(url).endswith("/users/sub-b"):
            return _Resp(
                200,
                {"id": "sub-b", "email": "", "username": "legacy-email:bob.example@example.test"},
            )
        if str(url).endswith("/users/sub-c"):
            return _Resp(404, {"error": "not_found"})
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.resolve_student_login_labels_by_sub(["sub-a", "sub-b", "sub-c"])

    assert out == {
        "sub-a": "alice.example",
        "sub-b": "bob.example",
        "sub-c": "Unbekannt",
    }
    assert any(url.endswith("/users/sub-a") for url in called_urls)
    assert not any("/roles/" in url for url in called_urls)


def test_resolve_student_login_labels_by_sub_falls_back_to_unknown_on_request_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        raise RuntimeError("directory offline")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.resolve_student_login_labels_by_sub(["sub-a"])

    assert out == {"sub-a": "Unbekannt"}


def test_resolve_live_student_names_by_sub_prefers_person_name_then_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        if str(url).endswith("/users/sub-a"):
            return _Resp(
                200,
                {
                    "id": "sub-a",
                    "firstName": "Anna",
                    "lastName": "Adler",
                    "email": "anna.adler@example.test",
                    "username": "anna.adler@example.test",
                },
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE_TTL_SECONDS", 60.0, raising=False)
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE", {}, raising=False)

    first = dir.resolve_live_student_names_by_sub(["sub-a"])
    second = dir.resolve_live_student_names_by_sub(["sub-a"])

    assert first == {"sub-a": "Anna Adler"}
    assert second == {"sub-a": "Anna Adler"}
    assert len(called_urls) == 1


def test_resolve_live_student_names_by_sub_falls_back_to_localpart_when_names_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        if str(url).endswith("/users/sub-a"):
            return _Resp(
                200,
                {"id": "sub-a", "firstName": "", "lastName": "", "email": "", "username": "legacy-email:anna.adler@example.test"},
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE", {}, raising=False)

    out = dir.resolve_live_student_names_by_sub(["sub-a"])

    assert out == {"sub-a": "anna.adler"}


def test_resolve_live_student_names_by_sub_uses_warm_cache_without_fetching_new_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    token_calls = 0

    def fake_token(self) -> str:  # type: ignore[override]
        nonlocal token_calls
        token_calls += 1
        return "dummy-token"

    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        if str(url).endswith("/users/sub-a"):
            return _Resp(
                200,
                {
                    "id": "sub-a",
                    "firstName": "Anna",
                    "lastName": "Adler",
                    "email": "anna.adler@example.test",
                    "username": "anna.adler@example.test",
                },
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(dir._KC, "token", fake_token)
    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE_TTL_SECONDS", 60.0, raising=False)
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE", {}, raising=False)

    first = dir.resolve_live_student_names_by_sub(["sub-a"])
    second = dir.resolve_live_student_names_by_sub(["sub-a"])

    assert first == {"sub-a": "Anna Adler"}
    assert second == {"sub-a": "Anna Adler"}
    assert token_calls == 1
    kc = dir._KC()
    assert called_urls == [f"{kc.base_url}/admin/realms/{kc.realm}/users/sub-a"]


def test_resolve_live_student_names_by_sub_prunes_expired_entries_and_caps_cache_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    now = 100.0
    token_calls = 0

    def fake_token(self) -> str:  # type: ignore[override]
        nonlocal token_calls
        token_calls += 1
        return "dummy-token"

    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        sid = str(url).rsplit("/", 1)[-1]
        return _Resp(
            200,
            {
                "id": sid,
                "firstName": sid.upper(),
                "lastName": "",
                "email": f"{sid}@example.test",
                "username": f"{sid}@example.test",
            },
        )

    monkeypatch.setattr(dir._KC, "token", fake_token)
    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(dir.time, "monotonic", lambda: now)
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE_TTL_SECONDS", 10.0, raising=False)
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE_MAX_ENTRIES", 2, raising=False)
    monkeypatch.setattr(
        dir,
        "_LIVE_STUDENT_NAME_CACHE",
        {
            "expired-a": (50.0, "Expired A"),
            "expired-b": (60.0, "Expired B"),
        },
        raising=False,
    )

    out = dir.resolve_live_student_names_by_sub(["sub-a", "sub-b", "sub-c"])

    assert out == {
        "sub-a": "SUB-A",
        "sub-b": "SUB-B",
        "sub-c": "SUB-C",
    }
    assert token_calls == 1
    kc = dir._KC()
    assert set(called_urls) == {
        f"{kc.base_url}/admin/realms/{kc.realm}/users/sub-a",
        f"{kc.base_url}/admin/realms/{kc.realm}/users/sub-b",
        f"{kc.base_url}/admin/realms/{kc.realm}/users/sub-c",
    }
    assert set(dir._LIVE_STUDENT_NAME_CACHE.keys()) == {"sub-b", "sub-c"}
    assert all(expires_at > now for expires_at, _label in dir._LIVE_STUDENT_NAME_CACHE.values())


def test_resolve_live_student_names_by_sub_404_falls_back_without_duplicate_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        return _Resp(404, {})

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE", {}, raising=False)

    out = dir.resolve_live_student_names_by_sub(["legacy-email:anna.adler@example.test"])

    assert out == {"legacy-email:anna.adler@example.test": "anna.adler"}
    kc = dir._KC()
    assert called_urls == [
        f"{kc.base_url}/admin/realms/{kc.realm}/users/legacy-email:anna.adler@example.test"
    ]


def test_live_student_name_cache_helpers_are_safe_under_parallel_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE", {}, raising=False)
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE_MAX_ENTRIES", 64, raising=False)
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE_TTL_SECONDS", 5.0, raising=False)

    errors: list[Exception] = []
    stop = False

    def writer() -> None:
        nonlocal stop
        try:
            idx = 0
            while not stop:
                dir._set_live_student_name_cache(f"sub-{idx}", f"Label {idx}")
                idx += 1
        except Exception as exc:  # pragma: no cover - regression guard
            errors.append(exc)
            stop = True

    def reader() -> None:
        nonlocal stop
        try:
            deadline = time.monotonic() + 0.2
            while time.monotonic() < deadline and not stop:
                dir._prune_live_student_name_cache()
                dir._get_live_student_name_cache("sub-1")
        except Exception as exc:  # pragma: no cover - regression guard
            errors.append(exc)
            stop = True
        finally:
            stop = True

    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)

    writer_thread.start()
    reader_thread.start()
    writer_thread.join()
    reader_thread.join()

    assert errors == []


def test_resolve_live_student_names_by_sub_resolves_uncached_subs_in_parallel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.identity_access.directory as dir  # type: ignore

    token_calls = 0
    active_calls = 0
    max_active_calls = 0
    lock = threading.Lock()

    def fake_token(self) -> str:  # type: ignore[override]
        nonlocal token_calls
        token_calls += 1
        return "dummy-token"

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        nonlocal active_calls, max_active_calls
        sid = str(url).rsplit("/", 1)[-1]
        with lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
        time.sleep(0.02)
        with lock:
            active_calls -= 1
        return _Resp(
            200,
            {
                "id": sid,
                "firstName": sid.upper(),
                "lastName": "",
                "email": f"{sid}@example.test",
                "username": f"{sid}@example.test",
            },
        )

    monkeypatch.setattr(dir._KC, "token", fake_token)
    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(dir, "_LIVE_STUDENT_NAME_CACHE", {}, raising=False)

    out = dir.resolve_live_student_names_by_sub(["sub-a", "sub-b", "sub-c"])

    assert out == {
        "sub-a": "SUB-A",
        "sub-b": "SUB-B",
        "sub-c": "SUB-C",
    }
    assert token_calls == 1
    assert max_active_calls >= 2
