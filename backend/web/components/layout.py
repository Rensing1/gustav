"""
Layout Component for GUSTAV

Main layout wrapper that combines all components into a complete HTML page.
"""

from typing import Optional, Dict, Any
from .base import Component
from .navigation import Navigation
from .breadcrumbs import Breadcrumbs


class Layout(Component):
    """Main layout component that assembles the complete page"""

    def __init__(
        self,
        title: str,
        content: str,
        user: Optional[Dict[str, Any]] = None,
        show_nav: bool = True,
        show_header: bool = True,
        current_path: str = "/"
    ):
        """
        Args:
            title: Page title (will be escaped)
            content: Main content HTML (pre-rendered components)
            user: Current user object (optional)
            show_nav: Whether to show navigation (default: True)
            show_header: Whether to show header (default: True)
            current_path: Current URL path for active navigation highlighting
        """
        self.title = title
        self.content = content
        self.user = user
        self.show_nav = show_nav
        self.show_header = show_header
        self.current_path = current_path

    def render(self) -> str:
        """Render the complete HTML document including navigation and chrome."""

        breadcrumb_html = Breadcrumbs(self.current_path).render() if self.show_nav else ""
        main_inner = self._render_main_inner(breadcrumb_html)
        # Render sub-components (Navigation includes sidebar now)
        # Pass current_path to Navigation for active link highlighting
        nav_html = Navigation(self.user, self.current_path).render() if self.show_nav else ""

        return f"""<!DOCTYPE html>
<html lang="de">
<head>
    {self._render_head()}
</head>
<body>
    <!-- Skip-Link für Barrierefreiheit (Tab-Taste macht ihn sichtbar) -->
    <a href="#main-content" class="skip-link">
        Zum Hauptinhalt springen
    </a>

    {nav_html}

    <!-- ARIA Live Region for dynamic announcements -->
    <div id="live-region" class="sr-only" role="status" aria-live="polite" aria-atomic="true">
        <!-- Dynamic messages will be inserted here for screen readers -->
    </div>

    <!-- Main Content Area (adjusted for sidebar) -->
    <main id="main-content" class="main-content" role="main">
        {main_inner}
    </main>
</body>
</html>"""

    def render_fragment(self) -> str:
        """Return the HTMX fragment that keeps the sidebar toggle in sync.

        Why:
            HTMX swaps should not duplicate the sidebar container; the JS toggle
            expects exactly one `#sidebar` element in the DOM.
        Parameters:
            Uses the Layout instance state (title/content/user/current_path).
        Behavior:
            - Renders the `<main id="main-content">` fragment identical to the
              full-page render.
            - Appends a single `<aside id="sidebar" hx-swap-oob="true">` when
              navigation is enabled so the sidebar updates out-of-band.
        Permissions:
            None. Callers must ensure the invoking route already enforced the
            correct access control (e.g., teacher-only dashboards).
        """
        breadcrumb_html = Breadcrumbs(self.current_path).render() if self.show_nav else ""
        main_inner = self._render_main_inner(breadcrumb_html)
        if not self.show_nav:
            return main_inner
        # Out-of-band sidebar swap keeps the existing toggle button and state.
        sidebar_oob = Navigation(self.user, self.current_path).render_aside(oob=True)
        return f"{main_inner}{sidebar_oob}"

    def _render_head(self) -> str:
        """Render the HTML head section"""
        return f"""
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="GUSTAV - KI-gestützte Lernplattform für Schulen">

    <!-- Security headers -->
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta http-equiv="X-Frame-Options" content="SAMEORIGIN">

    <title>{self.escape(self.title)} - GUSTAV</title>

    <!-- Favicon -->
    <link rel="icon" href="/static/favicon.ico">

    <!-- Custom CSS (no external dependencies) -->
    <link rel="stylesheet" href="/static/css/gustav.css?v=5">

    <!-- HTMX for interactivity (local copy) -->
    <SCRIPT src="/static/js/vendor/htmx.min.js"></SCRIPT>
    <!-- Sortable.js for drag-and-drop -->
    <SCRIPT src="/static/js/vendor/Sortable.min.js?v=4"></SCRIPT>
    <!-- HTMX Sortable Extension (local integration) -->
    <SCRIPT src="/static/js/vendor/sortable.js?v=4"></SCRIPT>

    <!-- Minimal custom JavaScript -->
    <SCRIPT src="/static/js/gustav.js?v=6" defer></SCRIPT>
    <!-- Learning uploads enhancement (toggle + upload-intents) -->
    <SCRIPT src="/static/js/learning_upload.js?v=2" defer></SCRIPT>
    """

    def _render_main_inner(self, breadcrumb_html: str) -> str:
        """Render the inner markup of the main content column.

        Returns only the children of <main> so HTMX fragment swaps can replace
        innerHTML without nesting <main> elements.
        """
        return f"""
        {breadcrumb_html}
        {self.content}

        <!-- Footer integrated into main content -->
        <footer class="content-footer" role="contentinfo" aria-label="Seitenfuß">
            <div class="footer-content">
                <p class="text-center text-muted">
                    <a href="/privacy" hx-get="/privacy" hx-target="#main-content">Datenschutz</a>
                    –
                    <a href="/imprint" hx-get="/imprint" hx-target="#main-content">Impressum</a>
                    –
                    <a href="https://github.com/Rensing1/gustav/" target="_blank" rel="noopener">GitHub</a>
                </p>
            </div>
        </footer>
        """
