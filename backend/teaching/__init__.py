"""
Teaching domain package.

Contains repository implementations for the Unterrichten bounded context.
"""

from __future__ import annotations

import sys

# Temporary compatibility while legacy tests still import `teaching`.
if __name__ == "backend.teaching":
    sys.modules.setdefault("teaching", sys.modules[__name__])
elif __name__ == "teaching":
    sys.modules.setdefault("backend.teaching", sys.modules[__name__])
