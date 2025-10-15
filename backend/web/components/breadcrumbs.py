"""
Breadcrumb component for GUSTAV

Generates a simple breadcrumb trail based on the current request path.
"""

from typing import List, Tuple, Dict, Optional
from .base import Component
from .navigation import ROUTE_MAP, ROUTE_PATTERNS


class Breadcrumbs(Component):
    """Server-rendered breadcrumb trail"""

    def __init__(self, current_path: str = "/"):
        self.current_path = current_path or "/"

    def render(self) -> str:
        """Render breadcrumb navigation"""
        crumbs = self._build_crumbs()
        if len(crumbs) <= 1:
            return ""

        items = []
        last_index = len(crumbs) - 1
        for index, (href, label) in enumerate(crumbs):
            escaped_label = self.escape(label)
            if index == last_index:
                items.append(
                    f'<li class="breadcrumb-item" aria-current="page">{escaped_label}</li>'
                )
            else:
                items.append(
                    f'''<li class="breadcrumb-item">
    <a href="{href}"
       hx-get="{href}"
       hx-target="#main-content"
       hx-push-url="true"
       class="breadcrumb-link">{escaped_label}</a>
</li>'''
                )

        return f"""<nav class="breadcrumb" aria-label="Breadcrumb">
    <ol>
        {''.join(items)}
    </ol>
</nav>"""

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #

    def _build_crumbs(self) -> List[Tuple[str, str]]:
        """Build crumb list as (href, label)"""
        path = self._sanitize_path(self.current_path)
        crumbs: List[Tuple[str, str]] = [("/", self._label_for_path("/"))]

        if path == "/":
            return crumbs

        segments = [segment for segment in path.strip("/").split("/") if segment]
        current = ""
        for segment in segments:
            current = f"{current}/{segment}".replace("//", "/")
            crumbs.append((current, self._label_for_path(current)))

        return crumbs

    def _label_for_path(self, path: str) -> str:
        """Return display label for a concrete path"""
        match = self._match_route(path)
        if match:
            pattern, meta, params = match
            template = meta.get("label_template")
            if template:
                try:
                    return template.format(**params)
                except KeyError:
                    # Fallback to static label if formatting fails
                    pass
            label = meta.get("label")
            if label:
                return label

        if path == "/":
            return "Startseite"

        segment = path.strip("/").split("/")[-1]
        return self._humanize(segment)

    @staticmethod
    def _sanitize_path(path: str) -> str:
        clean = path.split("?")[0].split("#")[0]
        return clean or "/"

    @staticmethod
    def _humanize(segment: str) -> str:
        if not segment:
            return "Startseite"
        cleaned = segment.replace("-", " ").replace("_", " ")

        if cleaned.isdigit():
            return f"ID {cleaned}"

        words = [word.capitalize() for word in cleaned.split() if word]
        return " ".join(words) if words else segment

    def _match_route(self, path: str) -> Optional[Tuple[str, Dict[str, str], Dict[str, str]]]:
        """Return (pattern, meta, params) for the best matching route"""
        for pattern in ROUTE_PATTERNS:
            params = self._extract_params(pattern, path)
            if params is not None:
                return pattern, ROUTE_MAP[pattern], params
        return None

    @staticmethod
    def _extract_params(pattern: str, path: str) -> Optional[Dict[str, str]]:
        """Extract path parameters if pattern matches"""
        pattern_clean = pattern.strip("/")
        path_clean = path.strip("/")

        if not pattern_clean:
            return {} if not path_clean else None

        pattern_parts = pattern_clean.split("/")
        path_parts = path_clean.split("/")
        if len(pattern_parts) != len(path_parts):
            return None

        params: Dict[str, str] = {}
        for pattern_part, path_part in zip(pattern_parts, path_parts):
            if pattern_part.startswith(":"):
                params[pattern_part[1:]] = path_part
            elif pattern_part == path_part:
                continue
            else:
                return None

        return params
