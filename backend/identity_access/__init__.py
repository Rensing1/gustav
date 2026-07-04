"""Identity access bounded-context package."""

from __future__ import annotations

import sys

# Temporary compatibility while legacy tests still import `identity_access`.
if __name__ == "backend.identity_access":
    sys.modules.setdefault("identity_access", sys.modules[__name__])
elif __name__ == "identity_access":
    sys.modules.setdefault("backend.identity_access", sys.modules[__name__])
