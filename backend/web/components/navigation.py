"""
Navigation Component for GUSTAV

Role-based navigation that adapts to user type (student/teacher/admin).
All links use HTMX for SPA-like navigation without page reloads.
"""

from typing import Optional, Dict, Any, List, Tuple, Set
from .base import Component

# ---------------------------------------------------------------------------
# Route registry
# ---------------------------------------------------------------------------

RouteMeta = Dict[str, str]

ROUTE_MAP: Dict[str, RouteMeta] = {
    "/": {"label": "Startseite"},
    "/dashboard": {"label": "Dashboard"},
    "/wissenschaft": {"label": "Wissenschaft"},
    "/courses": {"label": "Kurse"},
    "/courses/:course_id": {"label_template": "Kurs {course_id}"},
    "/courses/:course_id/lessons": {"label": "Lektionen"},
    "/courses/:course_id/lessons/:lesson_id": {"label_template": "Lektion {lesson_id}"},
    "/progress": {"label": "Fortschritt"},
    "/flashcards": {"label": "Karteikarten"},
    "/students": {"label": "Schüler"},
    "/analytics": {"label": "Analytics"},
    "/content": {"label": "Inhalte"},
    "/users": {"label": "Nutzerverwaltung"},
    "/system": {"label": "System"},
    "/settings": {"label": "Einstellungen"},
    "/about": {"label": "Über GUSTAV"},
    "/login": {"label": "Anmelden"},
}

ROUTE_PATTERNS: List[str] = sorted(
    ROUTE_MAP.keys(),
    key=lambda pattern: pattern.count("/"),
    reverse=True,
)


class Navigation(Component):
    """Navigation component with role-based menu items"""

    def __init__(self, user: Optional[Dict[str, Any]] = None, current_path: str = "/"):
        """
        Args:
            user: User dict with 'role' key (optional)
            current_path: The current URL path for active link highlighting
        """
        self.user = user
        self.current_path = current_path

    def render(self) -> str:
        """Render navigation based on user role with collapsible sidebar"""

        if not self.user:
            # Public navigation for non-authenticated users
            return self._render_public_nav()

        # Build navigation tree (supports future submenus)
        nav_tree = self._get_nav_tree()

        # Determine the single active href using "best prefix match"
        # Then mark parent as active if any child matches
        self._active_href = self._determine_active_href_from_tree(nav_tree)
        self._active_parents = self._determine_active_parents(nav_tree, self._active_href)

        # Build navigation HTML from tree
        links = [self._render_nav_item(item) for item in nav_tree]

        # Add logout link at the end
        links.append(self._render_logout())

        role_de = self._role_de(self.user.get("role")) if self.user else ""
        name = self.user.get("name", "") if self.user else ""
        return f"""
    <!-- Sidebar Toggle Button -->
    <button class="sidebar-toggle" data-action="sidebar-toggle" aria-label="Navigation umschalten">
        <span class="sidebar-toggle-icon">☰</span>
    </button>

    <!-- Collapsible Sidebar -->
    <aside class="sidebar" id="sidebar" aria-label="Seitenleiste">
        <nav class="sidebar-nav" role="navigation" aria-label="Hauptnavigation">
            <div class="sidebar-header">
                <span class="sidebar-logo" aria-hidden="true"></span>
                <span class="sidebar-title">GUSTAV</span>
            </div>

            <div class="sidebar-items">
                {''.join(links)}
            </div>

            <div class="sidebar-footer">
                <div class="user-info-compact">
                    <span class="nav-icon">👤</span>
                    <div class="nav-text">
                        <div class="user-name">{self.escape(name)}</div>
                        <div class="user-role">{self.escape(role_de)}</div>
                    </div>
                </div>
            </div>
        </nav>
    </aside>

    <!-- Mobile Overlay -->
    <div class="sidebar-overlay" data-action="sidebar-close"></div>"""

    def render_aside(self, oob: bool = False) -> str:
        """Render only the sidebar <aside> element (for OOB updates via HTMX)

        Args:
            oob: If True, adds hx-swap-oob="true" to enable out-of-band swap

        Returns:
            HTML string for the sidebar only
        """

        # Public navigation for non-authenticated users
        if not self.user:
            # Public sidebar (without toggle & overlay)
            return self._render_public_aside(oob=oob)

        nav_tree = self._get_nav_tree()
        self._active_href = self._determine_active_href_from_tree(nav_tree)
        self._active_parents = self._determine_active_parents(nav_tree, self._active_href)
        links = [self._render_nav_item(item) for item in nav_tree]
        # Ensure logout control is also present in OOB sidebar updates
        links.append(self._render_logout())

        oob_attr = ' hx-swap-oob="true"' if oob else ''
        role_de = self._role_de(self.user.get("role")) if self.user else ""
        name = self.user.get("name", "") if self.user else ""
        return f"""
    <aside class="sidebar" id="sidebar" aria-label="Seitenleiste"{oob_attr}>
        <nav class="sidebar-nav" role="navigation" aria-label="Hauptnavigation">
            <div class="sidebar-header">
                <span class="sidebar-logo" aria-hidden="true"></span>
                <span class="sidebar-title">GUSTAV</span>
            </div>

            <div class="sidebar-items">
                {''.join(links)}
            </div>

            <div class="sidebar-footer">
                <div class="user-info-compact">
                    <span class="nav-icon">👤</span>
                    <div class="nav-text">
                        <div class="user-name">{self.escape(name)}</div>
                        <div class="user-role">{self.escape(role_de)}</div>
                    </div>
                </div>
            </div>
        </nav>
    </aside>"""

    def _render_public_nav(self) -> str:
        """Navigation for non-authenticated users"""
        return f"""
    <!-- Sidebar Toggle Button -->
    <button class="sidebar-toggle" data-action="sidebar-toggle" aria-label="Navigation umschalten">
        <span class="sidebar-toggle-icon">☰</span>
    </button>

    <!-- Collapsible Sidebar (Public) -->
    <aside class="sidebar" id="sidebar" aria-label="Seitenleiste">
        <nav class="sidebar-nav" role="navigation" aria-label="Hauptnavigation">
            <div class="sidebar-header">
                <span class="sidebar-logo" aria-hidden="true"></span>
                <span class="sidebar-title">GUSTAV</span>
            </div>

            <div class="sidebar-items">
                {self._create_nav_link("/about", "Über GUSTAV", "ℹ️")}
                {self._create_nav_link("/login", "Anmelden", "🔑")}
            </div>
        </nav>
    </aside>

    <!-- Mobile Overlay -->
    <div class="sidebar-overlay" data-action="sidebar-close"></div>"""

    def _render_public_aside(self, oob: bool = False) -> str:
        """Public-only sidebar (aside element) for OOB updates"""
        oob_attr = ' hx-swap-oob="true"' if oob else ''
        return f"""
    <aside class="sidebar" id="sidebar" aria-label="Seitenleiste"{oob_attr}>
        <nav class="sidebar-nav" role="navigation" aria-label="Hauptnavigation">
            <div class="sidebar-header">
                <span class="sidebar-logo" aria-hidden="true"></span>
                <span class="sidebar-title">GUSTAV</span>
            </div>

            <div class="sidebar-items">
                {self._create_nav_link("/about", "Über GUSTAV", "ℹ️")}
                {self._create_nav_link("/login", "Anmelden", "🔑")}
            </div>
        </nav>
    </aside>"""

    def _get_nav_items(self) -> List[Tuple[str, str, str]]:
        """Legacy: flat list of items (kept for compatibility)"""
        role = self.user.get("role", "student")

        # Common items for all authenticated users
        items = [
            ("/", "Startseite", "🏠"),
            ("/dashboard", "Dashboard", "📊"),
            ("/wissenschaft", "Wissenschaft", "🔬"),  # Available for all roles
        ]

        # Role-specific items
        if role == "student":
            items.extend([
                ("/courses", "Meine Kurse", "📚"),
                ("/progress", "Fortschritt", "📈"),
                ("/flashcards", "Karteikarten", "🗂️"),
            ])

        elif role == "teacher":
            items.extend([
                ("/courses", "Kursverwaltung", "📚"),
                ("/students", "Schüler", "👥"),
                ("/analytics", "Analytics", "📈"),
                ("/content", "Inhalte erstellen", "✏️"),
            ])

        elif role == "admin":
            items.extend([
                ("/users", "Nutzerverwaltung", "👥"),
                ("/system", "System", "⚙️"),
                ("/analytics", "Analytics", "📈"),
            ])

        # Settings for all authenticated users
        items.append(("/settings", "Einstellungen", "⚙️"))

        return items

    def _get_nav_tree(self) -> List[Tuple[str, str, str, Optional[List[Tuple[str, str, str]]]]]:
        """Return navigation items with optional children (submenus)

        Structure: List of 4-tuples (href, text, icon, children)
        where children is either None or a list of (href, text, icon).
        For now we do not include children yet; this prepares the structure.
        """
        flat = self._get_nav_items()
        return [(href, text, icon, None) for href, text, icon in flat]

    def _determine_active_href_from_tree(self, nav_tree: List[Tuple[str, str, str, Optional[List[Tuple[str, str, str]]]]]) -> str:
        """Pick the single active href using best prefix match across tree items and children."""
        path = self.current_path or "/"
        best = "/"
        best_len = 0
        # Check parents and children
        for href, _text, _icon, children in nav_tree:
            # Parent exact
            if href == path:
                return href
            # Parent prefix
            if href != "/" and path.startswith(href) and len(href) > best_len:
                best = href
                best_len = len(href)
            # Children
            if children:
                for ch_href, _ct, _ci in children:
                    if ch_href == path:
                        return ch_href
                    if ch_href != "/" and path.startswith(ch_href) and len(ch_href) > best_len:
                        best = ch_href
                        best_len = len(ch_href)
        return best

    def _determine_active_parents(self, nav_tree: List[Tuple[str, str, str, Optional[List[Tuple[str, str, str]]]]], active_href: str) -> set:
        """Return set of parent hrefs to mark as active if a child is active.

        Rule: A parent is considered active if active_href starts with the parent's href (and parent != '/').
        """
        parents = set()
        for href, _text, _icon, children in nav_tree:
            if href != "/" and active_href.startswith(href):
                parents.add(href)
            if children:
                for ch_href, _ct, _ci in children:
                    if ch_href == active_href:
                        parents.add(href)
        return parents

    def _render_nav_item(self, item: Tuple[str, str, str, Optional[List[Tuple[str, str, str]]]]) -> str:
        """Render either a single link or a group with visible children."""
        href, text, icon, children = item
        # Parent is active if it equals active href or is in computed active parents
        parent_is_active = (href == getattr(self, "_active_href", None)) or (href in getattr(self, "_active_parents", set()))

        parent_link = self._create_nav_link(href, text, icon, is_active=parent_is_active, aria_current=(href == getattr(self, "_active_href", None)))

        if not children:
            return parent_link

        # Render children visibly (no collapsible behavior for now)
        child_links = []
        for ch_href, ch_text, ch_icon in children:
            ch_is_active = (ch_href == getattr(self, "_active_href", None))
            child_links.append(self._create_nav_link(ch_href, ch_text, ch_icon, is_active=ch_is_active, aria_current=ch_is_active))

        return f"""
        <div class="sidebar-group">
            {parent_link}
            <div class="sidebar-subitems">
                {''.join(child_links)}
            </div>
        </div>"""

    def _create_nav_link(self, href: str, text: str, icon: str = "", is_active: Optional[bool] = None, aria_current: Optional[bool] = None) -> str:
        """Create a navigation link with HTMX and active state highlighting

        Args:
            href: URL path
            text: Link text
            icon: Optional emoji icon

        Returns:
            HTML string for navigation link with active state if current
        """
        icon_html = f'<span class="nav-icon">{icon}</span>' if icon else ""

        # Check if this link is the single active href determined earlier
        if is_active is None:
            active_href = getattr(self, "_active_href", None)
            is_active = (active_href == href)

        # Add 'active' class if this is the current page
        active_class = " active" if is_active else ""

        # Add aria-current for accessibility
        if aria_current is None:
            aria_current = is_active
        aria_attr = ' aria-current="page"' if aria_current else ""

        return f"""
        <a href="{href}"
           hx-get="{href}"
           hx-target="#main-content"
           hx-push-url="true"
           hx-indicator="#loading-indicator"
           class="sidebar-link{active_class}"
           aria-label="{self.escape(text)}"
           data-tooltip="{self.escape(text)}"{aria_attr}>
            {icon_html}
            <span class="nav-text">{self.escape(text)}</span>
        </a>"""

    def _render_logout(self) -> str:
        """Render logout link as normal navigation to unified GET /auth/logout.

        Rationale: logout triggers IdP end-session which is cross-origin; use full
        page navigation instead of HTMX XHR.
        """
        return """
        <a href="/auth/logout"
           class="sidebar-link sidebar-logout"
           aria-label="Abmelden"
           data-tooltip="Abmelden">
            <span class="nav-icon">🚪</span>
            <span class="nav-text">Abmelden</span>
        </a>"""

    @staticmethod
    def _role_de(role: Optional[str]) -> str:
        mapping = {
            "teacher": "Lehrer",
            "student": "Schüler",
            "admin": "Administrator",
        }
        return mapping.get((role or "").lower(), "Nutzer")
