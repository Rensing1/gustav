"""
Service layer for the Teaching bounded context.

Holds use-case orchestration that remains independent of web frameworks.
"""

from __future__ import annotations

import sys

# Temporary compatibility while legacy tests still import `teaching.services`.
if __name__ == "backend.teaching.services":
    sys.modules.setdefault("teaching.services", sys.modules[__name__])
elif __name__ == "teaching.services":
    sys.modules.setdefault("backend.teaching.services", sys.modules[__name__])
for _parent_name, _attribute_name in (("teaching", "services"), ("backend.teaching", "services")):
    _parent = sys.modules.get(_parent_name)
    if _parent is not None:
        setattr(_parent, _attribute_name, sys.modules[__name__])
