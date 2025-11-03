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
        # We care about role listing endpoint only
        assert "/roles/student/users" in url
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

