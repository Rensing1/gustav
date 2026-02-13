"""
Identity Directory — search_users_by_name should page over role members so that
searches can find users not present in the first page.

Given:
- The first page of role members does not contain the searched name
- The second page contains a matching user
When:
- search_users_by_name(role='student', q='Zelda', limit=5)
Then:
- It returns the matching user from the next page.
"""
from __future__ import annotations

import types
import pytest


pytestmark = pytest.mark.anyio("asyncio")


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


def _mk_user(idx: int, name: str | None = None, username: str | None = None):
    return {
        "id": f"sub-{idx:04d}",
        "firstName": None,
        "lastName": None,
        "email": None,
        "username": username or f"user{idx:04d}",
        "attributes": {},
        "display_name": name or None,
    }


def test_directory_search_pages_over_role_members(monkeypatch: pytest.MonkeyPatch):
    import backend.identity_access.directory as dir  # type: ignore

    # Patch token production
    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)

    # Patch requests.get to simulate two pages of role members
    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        # We care about student role listing endpoints only
        assert (
            "/roles/student/users" in url
            or "/roles/default-roles-gustav/users" in url
        )
        if "/roles/default-roles-gustav/users" in url:
            return _Resp(200, [])
        first = int((params or {}).get("first", 0))
        maxn = int((params or {}).get("max", 200))
        if first == 0:
            # Return a page without our target
            data = [_mk_user(i) for i in range(0, maxn)]
            return _Resp(200, data)
        elif first == maxn:
            # Next page includes the target matching 'Zelda'
            data = [_mk_user(maxn), _mk_user(maxn + 1, name="Zelda Zed", username="zelda")]  # target
            return _Resp(200, data)
        else:
            return _Resp(200, [])

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.search_users_by_name(role="student", q="Zel", limit=5)
    subs = [it.get("sub") for it in out]
    names = [it.get("name") for it in out]
    assert any("Zelda" in (n or "") for n in names)
    assert any(s.startswith("sub-") for s in subs)


def test_directory_search_includes_default_role_members_for_student(monkeypatch: pytest.MonkeyPatch):
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        if "/roles/student/users" in url:
            return _Resp(200, [])
        if "/roles/default-roles-gustav/users" in url:
            return _Resp(200, [_mk_user(1, name="Fresh Student", username="fresh.student")])
        return _Resp(200, [])

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.search_users_by_name(role="student", q="fresh", limit=5)
    assert out == [{"sub": "sub-0001", "name": "Fresh Student"}]
    assert any("/roles/default-roles-gustav/users" in url for url in called_urls)


def test_directory_list_includes_default_role_members_for_student(monkeypatch: pytest.MonkeyPatch):
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    called_urls: list[str] = []

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        called_urls.append(str(url))
        if "/roles/student/users" in url:
            return _Resp(200, [])
        if "/roles/default-roles-gustav/users" in url:
            return _Resp(200, [_mk_user(2, name="Auto Student", username="auto.student")])
        return _Resp(200, [])

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.list_users_by_role(role="student", limit=20, offset=0)
    assert out == [{"sub": "sub-0002", "name": "Auto Student"}]
    assert any("/roles/default-roles-gustav/users" in url for url in called_urls)


def test_directory_search_retries_with_admin_fallback_token(monkeypatch: pytest.MonkeyPatch):
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    monkeypatch.setattr(dir._KC, "token_admin_fallback", lambda self: "admin-token")

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        auth = str((headers or {}).get("Authorization", ""))
        if "/roles/student/users" in url and "dummy-token" in auth:
            return _Resp(403, {"error": "forbidden"})
        if "/roles/student/users" in url:
            return _Resp(
                200,
                [
                    {
                        "id": "sub-1111",
                        "email": "sebastian.keyser@example.test",
                        "username": "sebastian.keyser@example.test",
                        "firstName": "",
                        "lastName": "",
                        "attributes": {},
                    }
                ],
            )
        if "/roles/default-roles-gustav/users" in url:
            return _Resp(200, [])
        return _Resp(200, [])

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.search_users_by_name(role="student", q="seb", limit=5)
    assert out == [{"sub": "sub-1111", "name": "Sebastian Keyser"}]


def test_directory_search_by_surname_works_after_admin_fallback(monkeypatch: pytest.MonkeyPatch):
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    monkeypatch.setattr(dir._KC, "token_admin_fallback", lambda self: "admin-token")

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        auth = str((headers or {}).get("Authorization", ""))
        if "/roles/student/users" in url and "dummy-token" in auth:
            return _Resp(403, {"error": "forbidden"})
        if "/roles/student/users" in url:
            return _Resp(
                200,
                [
                    {
                        "id": "sub-otto",
                        "email": "otto.mustermann@example.test",
                        "username": "otto.mustermann@example.test",
                        "firstName": "",
                        "lastName": "",
                        "attributes": {},
                    }
                ],
            )
        if "/roles/default-roles-gustav/users" in url:
            return _Resp(200, [])
        return _Resp(200, [])

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.search_users_by_name(role="student", q="mustermann", limit=10)
    assert out == [{"sub": "sub-otto", "name": "Otto Mustermann"}]


def test_directory_list_retries_with_admin_fallback_token(monkeypatch: pytest.MonkeyPatch):
    import backend.identity_access.directory as dir  # type: ignore

    monkeypatch.setattr(dir._KC, "token", _kc_token_stub)
    monkeypatch.setattr(dir._KC, "token_admin_fallback", lambda self: "admin-token")

    def fake_get(url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        auth = str((headers or {}).get("Authorization", ""))
        if "/roles/student/users" in url and "dummy-token" in auth:
            return _Resp(403, {"error": "forbidden"})
        if "/roles/student/users" in url:
            return _Resp(
                200,
                [
                    {
                        "id": "sub-student",
                        "email": "student@example.test",
                        "username": "student@example.test",
                        "firstName": "Stu",
                        "lastName": "Dent",
                        "attributes": {},
                    }
                ],
            )
        if "/roles/default-roles-gustav/users" in url:
            return _Resp(200, [])
        return _Resp(200, [])

    monkeypatch.setattr(dir, "requests", types.SimpleNamespace(get=fake_get))

    out = dir.list_users_by_role(role="student", limit=10, offset=0)
    assert out == [{"sub": "sub-student", "name": "Stu Dent"}]
